# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
The tool for triggering updates pushes.
"""

import click
import json
import glob

from collections import defaultdict
from fedora.client.bodhi import Bodhi2Client

import bodhi.notifications


@click.command()
@click.option('--releases', help='Push updates for specific releases')
#@click.option('--type', default=None, help='Push a specific type of update',
#        type=click.Choice(['security', 'bugfix', 'enhancement', 'newpackage']))
@click.option('--request', default='testing,stable',
        help='Push updates with a specific request (default: testing,stable)')
@click.option('--builds', help='Push updates for specific builds')
@click.option('--username', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--cert-prefix', default="shell",
              help="The prefix of a fedmsg cert used to sign the message.")
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@click.option('--resume', help='Resume one or more previously failed pushes',
              is_flag=True, default=False)
def push(username, password, cert_prefix, **kwargs):
    staging = kwargs.pop('staging')
    resume = kwargs.pop('resume')
    client = Bodhi2Client(username=username, password=password,
                          staging=staging)

    lockfiles = defaultdict(list)
    locked_updates = []
    if staging:
        locks = '/var/cache/bodhi/mashing/MASHING-*'
    else:
        locks = '/mnt/koji/mash/updates/MASHING-*'
    for lockfile in glob.glob(locks):
        with file(lockfile) as lock:
            state = json.load(lock)
        for update in state['updates']:
            lockfiles[lockfile].append(update)
            locked_updates.append(update)

    # If we're resuming a push
    if resume:
        updates = []
        for lockfile in lockfiles:
            doit = raw_input('Resume %s? (y/n)' % lockfile).strip().lower()
            if doit == 'n':
                continue

            for update in lockfiles[lockfile]:
                updates.append(update)
                click.echo(update)
    else:
        # release->request->updates
        releases = defaultdict(lambda: defaultdict(list))
        updates = []

        # Gather the list of updates based on the query parameters
        # Since there's currently no simple way to get a list of all updates with
        # any request, we'll take a comma/space-delimited list of them and query
        # one at a time.
        requests = kwargs['request'].replace(',', ' ').split(' ')
        del(kwargs['request'])
        for request in requests:
            resp = client.query(request=request, **kwargs)
            for update in resp.updates:
                # Skip locked updates that are in a current push
                if update.locked:
                    if update.title in locked_updates:
                        continue
                    # Warn about locked updates that aren't a part of a push and
                    # push them again.
                    else:
                        click.echo('Warning: %s is locked but not in a push' %
                                   update.title)

                updates.append(update.title)
                for build in update.builds:
                    releases[update.release.name][request].append(build.nvr)
            while resp.page < resp.pages:
                resp = client.query(request=request, page=resp.page + 1, **kwargs)
                for update in resp.updates:
                    updates.append(update.title)
                    for build in update.builds:
                        releases[update.release.name][request].append(build.nvr)

            # Write out a file that releng uses to pass to sigul for signing
            # TODO: in the future we should integrate signing into the workflow
            for release in releases:
                output_filename = request.title() + '-' + release
                click.echo(output_filename + '\n==========')
                with file(output_filename, 'w') as out:
                    for build in releases[release][request]:
                        out.write(build + '\n')
                        click.echo(build)
                click.echo('')

    doit = raw_input('Push these %d updates? (y/n)' % len(updates)).lower().strip()
    if doit == 'y':
        click.echo('\nSending masher.start fedmsg')
        # Because we're a script, we want to send to the fedmsg-relay,
        # that's why we say active=True
        bodhi.notifications.init(active=True, cert_prefix=cert_prefix)
        bodhi.notifications.publish(
            topic='masher.start',
            msg=dict(
                updates=list(updates),
                resume=resume,
                agent=username,
            ),
            force=True,
        )
    else:
        click.echo('\nAborting push')


if __name__ == '__main__':
    push()
