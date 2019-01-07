# Copyright © 2017-2018 Red Hat, Inc.
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
This module contains tests for the bodhi.server.scripts.monitor_composes module.
"""
import json
import mock

from click import testing

from bodhi.server import models
from bodhi.server.scripts import monitor_composes
from bodhi.tests.server.base import BaseTestCase
from bodhi.tests.utils import compare_output


@mock.patch('bodhi.server.scripts.monitor_composes.initialize_db', mock.MagicMock())
@mock.patch('bodhi.server.scripts.monitor_composes.buildsys.setup_buildsystem', mock.MagicMock())
class TestMonitor(BaseTestCase):
    """This class contains tests for the monitor() function."""

    def test_monitor_no_composes(self):
        """Ensure correct output from the monitor function."""
        runner = testing.CliRunner()

        r = runner.invoke(monitor_composes.monitor)

        self.assertEqual(r.exit_code, 0)
        self.assertEqual(
            r.output,
            ("This utility has been deprecated. Please use 'bodhi composes list' instead.\nLocked "
             "updates: 0\n\n"))

    def test_monitor_with_composes(self):
        """Ensure correct output from the monitor function."""
        runner = testing.CliRunner()
        update = models.Update.query.one()
        update.locked = True
        update.status = models.UpdateStatus.pending
        update.request = models.UpdateRequest.testing
        compose_1 = models.Compose(
            release=update.release, request=update.request, state=models.ComposeState.notifying,
            checkpoints=json.dumps({'check_1': True, 'check_2': True}))
        ejabberd = self.create_update([u'ejabberd-16.09-4.fc17'])
        ejabberd.locked = True
        ejabberd.status = models.UpdateStatus.testing
        ejabberd.request = models.UpdateRequest.stable
        ejabberd.type = models.UpdateType.security
        compose_2 = models.Compose(
            release=ejabberd.release, request=ejabberd.request, state=models.ComposeState.failed,
            error_message=u'y r u so mean nfs')
        self.db.add(compose_1)
        self.db.add(compose_2)
        self.db.flush()

        r = runner.invoke(monitor_composes.monitor)

        self.assertEqual(r.exit_code, 0)
        EXPECTED_OUTPUT = (
            "This utility has been deprecated. Please use 'bodhi composes list' instead.\n"
            'Locked updates: 2\n\n<Compose: F17 stable>\n\tstate: failed\n\tstate_date: {}\n\t'
            'security: True\n\terror_message: y r u so mean nfs\n\tcheckpoints: \n\t'
            'len(updates): 1\n\n<Compose: F17 testing>\n\tstate: notifying\n\tstate_date: {}\n\t'
            'security: False\n\tcheckpoints: check_1, check_2\n\tlen(updates): 1\n\n')
        self.assertTrue(compare_output(
                        r.output,
                        EXPECTED_OUTPUT.format(compose_2.state_date, compose_1.state_date)
                        ))
