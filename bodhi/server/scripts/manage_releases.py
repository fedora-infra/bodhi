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
managereleases.py create --name F23 --long-name "Fedora 23" --id-prefix FEDORA --version 23 \
--branch f23 --dist-tag f23 --stable-tag f23-updates --testing-tag f23-updates-testing \
--candidate-tag f23-updates-candidate --pending-stable-tag f23-updates-pending \
--pending-testing-tag f23-updates-testing-pending --override-tag f23-override --state pending
"""

import sys
import munch

import click

from fedora.client.bodhi import Bodhi2Client


@click.group()
def main():
    pass


@main.command()
@click.option('--username', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--name', help='Release name (eg: F20)')
@click.option('--long-name', help='Long release name (eg: "Fedora 20")')
@click.option('--id-prefix', help='Release prefix (eg: FEDORA)')
@click.option('--version', help='Release version number (eg: 20)')
@click.option('--branch', help='Git branch name (eg: f20)')
@click.option('--dist-tag', help='Koji dist tag (eg: f20)')
@click.option('--stable-tag', help='Koji stable tag (eg: f20-updates)')
@click.option('--testing-tag',
              help='Koji testing tag (eg: f20-updates-testing)')
@click.option('--candidate-tag',
              help='Koji candidate tag (eg: f20-updates-candidate)')
@click.option('--pending-stable-tag',
              help='Koji pending tag (eg: f20-updates-pending)')
@click.option('--pending-testing-tag',
              help='Koji pending testing tag (eg: f20-updates-testing-testing)')
@click.option('--override-tag', help='Koji override tag (eg: f20-override)')
@click.option('--state', type=click.Choice(['disabled', 'pending', 'current',
                                            'archived']),
              help='The state of the release')
def create(username, password, **kwargs):
    client = Bodhi2Client(username=username, password=password)
    kwargs['csrf_token'] = client.csrf()

    save(client, **kwargs)


@main.command()
@click.option('--username', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--name', help='Release name (eg: F20)')
@click.option('--new-name', help='New release name (eg: F20)')
@click.option('--long-name', help='Long release name (eg: "Fedora 20")')
@click.option('--id-prefix', help='Release prefix (eg: FEDORA)')
@click.option('--version', help='Release version number (eg: 20)')
@click.option('--branch', help='Git branch name (eg: f20)')
@click.option('--dist-tag', help='Koji dist tag (eg: f20)')
@click.option('--stable-tag', help='Koji stable tag (eg: f20-updates)')
@click.option('--testing-tag',
              help='Koji testing tag (eg: f20-updates-testing)')
@click.option('--candidate-tag',
              help='Koji candidate tag (eg: f20-updates-candidate)')
@click.option('--pending-stable-tag',
              help='Koji pending tag (eg: f20-updates-pending)')
@click.option('--pending-testing-tag',
              help='Koji pending testing tag (eg: f20-updates-testing-testing)')
@click.option('--override-tag', help='Koji override tag (eg: f20-override)')
@click.option('--state', type=click.Choice(['disabled', 'pending', 'current',
                                            'archived']),
              help='The state of the release')
def edit(username, password, **kwargs):
    client = Bodhi2Client(username=username, password=password)
    csrf = client.csrf()

    edited = kwargs.pop('name')

    if edited is None:
        print("ERROR: Please specify the name of the release to edit")
        return

    res = client.send_request('releases/%s' % edited, verb='GET', auth=True)

    data = munch.unmunchify(res)

    if 'errors' in data:
        print_errors(data)

    data['edited'] = edited
    data['csrf_token'] = csrf

    new_name = kwargs.pop('new_name')

    if new_name is not None:
        data['name'] = new_name

    for k, v in kwargs.items():
        if v is not None:
            data[k] = v

    save(client, **data)


@main.command()
@click.argument('name')
def info(name):
    client = Bodhi2Client()

    res = client.send_request('releases/%s' % name, verb='GET', auth=False)

    if 'errors' in res:
        print_errors(res)

    else:
        print('Release:')
        print_release(res)


def save(client, **kwargs):
    res = client.send_request('releases/', verb='POST', auth=True,
                              data=kwargs)

    if 'errors' in res:
        print_errors(res)

    else:
        print("Saved release:")
        print_release(res)


def print_release(release):
        print("  Name:                %s" % release['name'])
        print("  Long Name:           %s" % release['long_name'])
        print("  Version:             %s" % release['version'])
        print("  Branch:              %s" % release['branch'])
        print("  ID Prefix:           %s" % release['id_prefix'])
        print("  Dist Tag:            %s" % release['dist_tag'])
        print("  Stable Tag:          %s" % release['stable_tag'])
        print("  Testing Tag:         %s" % release['testing_tag'])
        print("  Candidate Tag:       %s" % release['candidate_tag'])
        print("  Pending Signing Tag: %s" % release['pending_signing_tag'])
        print("  Pending Testing Tag: %s" % release['pending_testing_tag'])
        print("  Pending Stable Tag:  %s" % release['pending_stable_tag'])
        print("  Override Tag:        %s" % release['override_tag'])
        print("  State:               %s" % release['state'])


def print_errors(data):
    for error in data['errors']:
        print("ERROR: %s" % error['description'])

    sys.exit(1)


if __name__ == '__main__':
    main()
