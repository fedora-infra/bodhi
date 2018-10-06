# Copyright (c) 2018 Red Hat, Inc. and Sebastian Wojciechowski
#
# This file is part of Bodhi.
#
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
"""This script will print out SAR data for a FAS account."""

import json
import sys

import click
import sqlalchemy

from bodhi.server import config, initialize_db, models


def print_human_readable_format(sar_data):
    """
    Print user data in human readable format.

    Args:
        sar_data (dict): User data to be printed.
    """
    header_start = "==========>"
    header_stop = "<=========="
    chapter_start = "---->"
    chapter_stop = "<----"

    for user in sar_data:
        click.echo("{} User account data for: {} {}\n".format(
            header_start, sar_data[user]['name'], header_stop
        ))
        click.echo("email: {}".format(sar_data[user]['email']))
        click.echo("groups: {}".format(sar_data[user]['groups']))
        click.echo("popups: {}".format(sar_data[user]['show_popups']))

        click.echo("\n{} Comments: {}".format(chapter_start, chapter_stop))
        for idx, comment in enumerate(sar_data[user]['comments'], 1):
            click.echo("\nComment no {}:".format(idx))
            for item in sorted(comment):
                click.echo("{}: {}".format(item, comment[item]))

        click.echo("\n{} Updates: {}".format(chapter_start, chapter_stop))
        for idx, update in enumerate(sar_data[user]['updates'], 1):
            click.echo("\nUpdate no {}:".format(idx))
            for item in sorted(update):
                click.echo("{}: {}".format(item, update[item]))


@click.command()
@click.option('--username', envvar='SAR_USERNAME', required=True,
              help='The username that sar data should be gathered.')
@click.option('--human-readable', default=False, is_flag=True,
              help='Print user data in human readable format.'
              ' The script defaults to JSON output.'
              )
@click.version_option(message='%(version)s')
def get_user_data(username, human_readable):
    """Get username SAR data."""
    initialize_db(config.config)

    sar_data = {}

    try:
        user = models.User.query.filter_by(name=username).one()
    except sqlalchemy.orm.exc.NoResultFound:
        if human_readable:
            click.echo("User not found.")
        sys.exit(0)

    sar_data[user.name] = {}
    sar_data[user.name]['comments'] = [
        {'karma': c.karma, 'karma_critpath': c.karma_critpath, 'text': c.text,
         'anonymous': c.anonymous, 'timestamp': c.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
         'update_alias': c.update.alias, 'username': c.user.name}
        for c in user.comments]
    sar_data[user.name]['email'] = user.email
    sar_data[user.name]['groups'] = [g.name for g in user.groups]
    sar_data[user.name]['name'] = user.name
    sar_data[user.name]['show_popups'] = user.show_popups
    sar_data[user.name]['updates'] = [
        {'autokarma': u.autokarma, 'stable_karma': u.stable_karma,
         'unstable_karma': u.unstable_karma, 'requirements': u.requirements,
         'require_bugs': u.require_bugs, 'require_testcases': u.require_testcases,
         'notes': u.notes, 'type': str(u.type), 'severity': str(u.severity),
         'suggest': str(u.suggest), 'close_bugs': u.close_bugs, 'alias': u.alias,
         'builds': [b.nvr for b in u.builds], 'release_name': u.release.name,
         'bugs': [b.bug_id for b in u.bugs], 'user': u.user.name,
         'date_submitted': u.date_submitted.strftime('%Y-%m-%d %H:%M:%S')}
        for u in user.updates]

    if human_readable:
        print_human_readable_format(sar_data)
    else:
        click.echo(json.dumps(sar_data, sort_keys=True))


if __name__ == '__main__':
    get_user_data()
