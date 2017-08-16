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
import click
from sqlalchemy.sql.expression import false

from bodhi.server import config, initialize_db, models, Session
from bodhi.server.util import greenwave_api_post


@click.command()
@click.version_option(message='%(version)s')
def check():
    """Check the enforced policies by Greenwave for each open update."""
    initialize_db(config.config)
    session = Session()

    updates = models.Update.query.filter(models.Update.pushed == false())\
        .filter(models.Update.status.in_(
                [models.UpdateStatus.pending, models.UpdateStatus.testing]))
    for update in updates:
        data = {
            'product_version': update.product_version,
            'decision_context': u'bodhi_update_push_stable',
            'subject': update.greenwave_subject
        }
        api_url = '{}/decision'.format(
            config.config.get('greenwave_api_url').rstrip('/'))

        try:
            decision = greenwave_api_post(api_url, data)
            if decision['policies_satisified']:
                # If an unrestricted policy is applied and no tests are required
                # on this update, let's set the test gating as ignored in Bodhi.
                if decision['summary'] == 'no tests are required':
                    update.test_gating_status = models.TestGatingStatus.ignored
                else:
                    update.test_gating_status = models.TestGatingStatus.passed
            else:
                update.test_gating_status = models.TestGatingStatus.failed
            update.greenwave_summary_string = decision['summary']
            if session.is_modified(update):
                session.commit()
        except Exception as e:
            # If there is a problem talking to Greenwave server, print the error.
            click.echo(str(e))
            session.rollback()


if __name__ == '__main__':
    check()
