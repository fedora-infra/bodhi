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
"""This module contains tests for the bodhi.server.scripts.check_policies module."""

from click import testing
from mock import patch

from bodhi.server import models
from bodhi.server.scripts import check_policies
from bodhi.tests.server.base import BaseTestCase
from bodhi.server.config import config


class TestCheckPolicies(BaseTestCase):
    """This class contains tests for the check_policies() function."""
    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_satisfied(self):
        """Assert correct behavior when the policies enforced by Greenwave are satisfied"""
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        self.db.commit()
        with patch('bodhi.server.scripts.check_policies.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisified': True,
                'summary': 'All tests passed',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': []
            }
            mock_greenwave.return_value = greenwave_response
            result = runner.invoke(check_policies.check, [])
            self.assertEqual(result.exit_code, 0)
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            self.assertEqual(update.test_gating_status, models.TestGatingStatus.passed)
            self.assertEqual(update.greenwave_summary_string, 'All tests passed')

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_unsatisfied(self):
        """Assert correct behavior when the policies enforced by Greenwave are unsatisfied"""
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        self.db.commit()
        with patch('bodhi.server.scripts.check_policies.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisified': False,
                'summary': '1 of 2 tests are failed',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [{
                    'item': "glibc-1.0-1.f26",
                    'result_id': "123",
                    'testcase': 'dist.depcheck',
                    'type': 'test-result-failed'
                }]
            }
            mock_greenwave.return_value = greenwave_response
            result = runner.invoke(check_policies.check, [])
            self.assertEqual(result.exit_code, 0)
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            self.assertEqual(update.test_gating_status, models.TestGatingStatus.failed)
            self.assertEqual(update.greenwave_summary_string, '1 of 2 tests are failed')

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_no_policies_enforced(self):
        """
        Assert correct behavior when policies are not enforced.

        When test gating is disabled, each Update's test_gating_status will be None.
        """
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        update.test_gating_status = None
        self.db.commit()
        with patch('bodhi.server.scripts.check_policies.greenwave_api_post') as mock_greenwave:
            mock_greenwave.return_value = RuntimeError('The error was blablabla')

            result = runner.invoke(check_policies.check, [])

        self.assertEqual(result.exit_code, 0)
        update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
        # The test_gating_status should still be None.
        self.assertTrue(update.test_gating_status is None)

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_unrestricted_policy(self):
        """Assert correct behavior when an unrestricted policy is applied"""
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        self.db.commit()
        with patch('bodhi.server.scripts.check_policies.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisified': True,
                'summary': 'no tests are required',
                'applicable_policies': ['bodhi-unrestricted'],
            }
            mock_greenwave.return_value = greenwave_response
            result = runner.invoke(check_policies.check, [])
            self.assertEqual(result.exit_code, 0)
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            self.assertEqual(update.test_gating_status, models.TestGatingStatus.ignored)
            self.assertEqual(update.greenwave_summary_string, 'no tests are required')
