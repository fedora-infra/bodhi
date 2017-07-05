# -*- coding: utf-8 -*-
# Copyright © 2017 Caleigh Runge-Hottman
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

from bodhi.server import models
from bodhi.server.scripts import dequeue_stable
from bodhi.tests.server.base import BaseTestCase


class TestDequeueStable(BaseTestCase):
    """
    This class contains tests for the dequeue_stable() function.
    """
    def test_dequeue_stable(self):
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

    def test_dequeue_stable_exception(self):
        """
        Assert that a locked update triggers an exception, and doesn't move to stable.
        """
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.request = models.UpdateRequest.batched
        self.db.commit()

        result = runner.invoke(dequeue_stable.dequeue_stable, [])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, u"Can't change the request on a locked update\n")
