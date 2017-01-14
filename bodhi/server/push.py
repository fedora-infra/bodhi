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
The CLI tool for triggering update pushes.
"""
from collections import defaultdict
from datetime import datetime
import glob
import json

from sqlalchemy.sql import or_
import click

from bodhi.server.models import Build, get_db_factory, Release, ReleaseState, Update, UpdateRequest
import bodhi.server.notifications


@click.command()
@click.option('--builds', help='Push updates for a comma-separated list of builds')
@click.option('--cert-prefix', default="shell",
              help="The prefix of a fedmsg cert used to sign the message")
@click.option('--releases', help=('Push updates for a comma-separated list of releases (default: '
                                  'current and pending releases)'))
@click.option('--request', default='testing,stable',
              help='Push updates with a specific request (default: testing,stable)')
@click.option('--resume', help='Resume one or more previously failed pushes',
              is_flag=True, default=False)
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@click.option('--username', envvar='USERNAME', prompt=True)
@click.version_option(message='%(version)s')
def push(username, cert_prefix, **kwargs):
    staging = kwargs.pop('staging')
    resume = kwargs.pop('resume')

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

    update_titles = None

    with get_db_factory()() as session:
        updates = []
        # If we're resuming a push
        if resume:
            for lockfile in lockfiles:
                if not click.confirm('Resume {}?'.format(lockfile)):
                    continue

                for update in lockfiles[lockfile]:
                    update = session.query(Update).filter(Update.title == update).first()
                    updates.append(update)
        else:
            # Accept both comma and space separated request list
            requests = kwargs['request'].replace(',', ' ').split(' ')
            requests = [UpdateRequest.from_string(val) for val in requests]

            query = session.query(Update).filter(Update.request.in_(requests))

            if kwargs.get('builds'):
                query = query.join(Update.builds)
                query = query.filter(
                    or_(*[Build.nvr == build for build in kwargs['builds'].split(',')]))

            query = _filter_releases(session, query, kwargs.get('releases'))

            for update in query.all():
                # Skip locked updates that are in a current push
                if update.locked:
                    if update.title in locked_updates:
                        continue
                    # Warn about locked updates that aren't a part of a push and
                    # push them again.
                    else:
                        click.echo('Warning: %s is locked but not in a push' %
                                   update.title)

                # Skip unsigned updates (this checks that all builds in the update are signed)
                if not update.signed:
                    click.echo('Warning: %s has unsigned builds and has been skipped' %
                               update.title)
                    continue

                updates.append(update)

        for update in updates:
            click.echo(update.title)

        if updates:
            click.confirm('Push these {:d} updates?'.format(len(updates)), abort=True)
            click.echo('\nLocking updates...')
            for update in updates:
                update.locked = True
                update.date_locked = datetime.utcnow()
        else:
            click.echo('\nThere are no updates to push.')

        update_titles = list([update.title for update in updates])

    if update_titles:
        click.echo('\nSending masher.start fedmsg')
        # Because we're a script, we want to send to the fedmsg-relay,
        # that's why we say active=True
        bodhi.server.notifications.init(active=True, cert_prefix=cert_prefix)
        bodhi.server.notifications.publish(
            topic='masher.start',
            msg=dict(
                updates=update_titles,
                resume=resume,
                agent=username,
            ),
            force=True,
        )


def _filter_releases(session, query, releases=None):
    """
    Apply a filter() transformation to the given query on Updates to filter updates that match the
    given releases argument. If releases evaluates "Falsey", this function will filter for Updates
    that are part of a current Release.

    :param session:  The database session
    :param query:    An Update query that we want to modify by filtering based on Releases
    :param releases: A comma-separated string of release names

    :returns:        A filtered version of query with an additional filter based on releases.
    """
    # We will store models.Release object here that we want to filter by
    _releases = []

    if releases:
        for r in releases.split(','):
            release = session.query(Release).filter(
                or_(Release.name == r,
                    Release.name == r.upper(),
                    Release.version == r)).first()
            if not release:
                raise click.BadParameter('Unknown release: %s' % r)
            else:
                _releases.append(release)
    else:
        # Since the user didn't ask for specific Releases, let's just filter for releases that are
        # current or pending.
        _releases = session.query(Release).filter(or_(Release.state == ReleaseState.current,
                                                      Release.state == ReleaseState.pending))

    return query.filter(or_(*[Update.release == r for r in _releases]))


if __name__ == '__main__':
    push()
