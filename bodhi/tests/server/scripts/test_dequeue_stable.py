# -*- coding: utf-8 -*-
# Copyright © 2017 Caleigh Runge-Hottman and Red Hat, Inc.
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
This module contains tests for the bodhi.server.scripts.dequeue_stable module.
"""
from datetime import datetime, timedelta

from click import testing
import mock

from bodhi.server import config, models
from bodhi.server.scripts import dequeue_stable
from bodhi.tests.server.base import BaseTestCase


@mock.patch('bodhi.server.scripts.dequeue_stable.Session.remove')
class TestDequeueStable(BaseTestCase):
    """
    This class contains tests for the dequeue_stable() function.
    """
    def test_bad_update_doesnt_block_others(self, remove):
        """
        Assert that one bad update in the set of batched updates doesn't block the others.
        """
        runner = testing.CliRunner()
        update_1 = models.Update.query.first()
        update_1_title = update_1.title
        update_1.request = models.UpdateRequest.batched
        update_1.locked = False
        update_1.date_testing = datetime.utcnow() - timedelta(days=7)
        build_2 = models.RpmBuild(nvr='bodhi-3.1.0-1.fc17', package=update_1.builds[0].package)
        self.db.add(build_2)
        update_2 = models.Update(
            title=build_2.nvr, builds=[build_2], type=models.UpdateType.enhancement, notes='blah',
            status=models.UpdateStatus.testing, request=models.UpdateRequest.batched,
            user=update_1.user, release=update_1.release)
        update_2_title = update_2.title
        self.db.add(update_2)
        self.db.commit()

        result = runner.invoke(dequeue_stable.dequeue_stable, [])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(config.config['not_yet_tested_msg'] in result.output)
        self.assertEqual(models.Update.query.filter_by(title=update_1_title).one().request,
                         models.UpdateRequest.stable)
        # set_request() rejected this update since it hasn't met testing requirements.
        self.assertEqual(models.Update.query.filter_by(title=update_2_title).one().request,
                         models.UpdateRequest.batched)
        # It should also have received a stern comment from Bodhi.
        c = models.Update.query.filter_by(title=update_2_title).one().comments[-1]
        self.assertEqual(c.user.name, 'bodhi')
        self.assertEqual(
            c.text,
            'Bodhi is unable to request this update for stabilization: {}'.format(
                config.config['not_yet_tested_msg']))
        remove.assert_called_once_with()

    def test_dequeue_stable(self, remove):
        """
        Assert that dequeue_stable moves only the batched updates to stable.
        """
        runner = testing.CliRunner()

        update = self.db.query(models.Update).all()[0]
        update.request = models.UpdateRequest.batched
        update.locked = False
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        self.db.commit()

        result = runner.invoke(dequeue_stable.dequeue_stable, [])
        self.assertEqual(result.exit_code, 0)

        update = self.db.query(models.Update).all()[0]
        self.assertEqual(update.request, models.UpdateRequest.stable)
        remove.assert_called_once_with()

    def test_dequeue_stable_exception(self, remove):
        """
        Assert that a failure to query the db is printed and raised.
        """
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.request = models.UpdateRequest.batched
        self.db.commit()

        # Let's simulate an error connecting to the db.
        with mock.patch('bodhi.server.scripts.dequeue_stable.Session') as Session:
            Session.return_value.query.side_effect = IOError("You can't haz network.")
            result = runner.invoke(dequeue_stable.dequeue_stable, [])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, "You can't haz network.\n")
        Session.remove.assert_called_once_with()
