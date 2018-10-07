# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc.
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

"""
Check the enforced policies by Greenwave for each open update.

Ideally, this should be done in a fedmsg consumer but we currently do not have any
messages in the message bus yet.
"""
import logging

import click

from bodhi.server import config, initialize_db, models, Session


logger = logging.getLogger('check-policies')
logging.basicConfig(level=logging.INFO)


@click.command()
@click.version_option(message='%(version)s')
def check():
    """Check the enforced policies by Greenwave for each open update."""
    initialize_db(config.config)
    session = Session()

    updates = models.Update.query.filter(
        models.Update.status.in_(
            [models.UpdateStatus.pending, models.UpdateStatus.testing])
    ).filter(
        models.Update.release_id == models.Release.id
    ).filter(
        models.Release.state.in_(
            [models.ReleaseState.current, models.ReleaseState.pending])
    ).order_by(
        # Check the older updates first so there is more time for the newer to
        # get their test results
        models.Update.id.asc()
    )

    for update in updates:
        try:
            update.update_test_gating_status()
            session.commit()
        except Exception as e:
            # If there is a problem talking to Greenwave server, print the error.
            click.echo(str(e))
            session.rollback()


if __name__ == '__main__':
    check()
