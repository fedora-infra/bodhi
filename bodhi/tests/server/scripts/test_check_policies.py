# Copyright © 2017-2019 Red Hat, Inc. and others.
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

from unittest.mock import patch
import datetime

from click import testing

from bodhi.server import models
from bodhi.server.scripts import check_policies
from bodhi.tests.server.base import BasePyTestCase
from bodhi.server.config import config


class TestCheckPolicies(BasePyTestCase):
    """This class contains tests for the check_policies() function."""
    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_satisfied(self):
        """Assert correct behavior when the policies enforced by Greenwave are satisfied"""
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': True,
                'summary': 'All tests passed',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': []
            }
            mock_greenwave.return_value = greenwave_response
            result = runner.invoke(check_policies.check, [])
            assert result.exit_code == 0
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.passed

        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_stable',
            'subject': [
                {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                 'type': 'bodhi_update'}],
            'verbose': False
        }
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_pending_satisfied(self):
        """Assert that Updates whose status is pending are checked against
        greenwave with the ``bodhi_update_push_testing`` decision context. """
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.pending
        self.db.commit()
        with patch('bodhi.server.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': True,
                'summary': 'All tests passed',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': []
            }
            mock_greenwave.return_value = greenwave_response
            result = runner.invoke(check_policies.check, [])
            assert result.exit_code == 0
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.passed

        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_testing',
            'subject': [
                {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                 'type': 'bodhi_update'}],
            'verbose': False,
        }
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_unsatisfied(self):
        """Assert correct behavior when the policies enforced by Greenwave are unsatisfied"""
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': '1 of 2 tests are failed',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': 'glibc-1.0-1.f26', 'type': 'koji_build'},
                     'type': 'test-result-missing', 'scenario': None},
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': update.alias, 'type': 'bodhi_update'},
                     'type': 'test-result-missing', 'scenario': None}]}
            mock_greenwave.return_value = greenwave_response
            result = runner.invoke(check_policies.check, [])
            assert result.exit_code == 0
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.failed
            # Check for the comment
            expected_comment = "This update's test gating status has been changed to 'failed'."
            assert update.comments[-1].text == expected_comment

        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_stable',
            'subject': [
                {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                 'type': 'bodhi_update'}],
            'verbose': False
        }
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_no_policies_enforced(self):
        """
        Assert correct behavior when policies are not enforced.

        When test gating is disabled, each Update's test_gating_status will be None.
        """
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        update.test_gating_status = None
        self.db.commit()
        with patch('bodhi.server.util.greenwave_api_post') as mock_greenwave:
            mock_greenwave.return_value = RuntimeError('The error was blablabla')

            result = runner.invoke(check_policies.check, [])

        assert result.exit_code == 0
        update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
        # The test_gating_status should still be None.
        assert update.test_gating_status is None
        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_stable',
            'subject': [
                {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                 'type': 'bodhi_update'}],
            'verbose': False
        }
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_pushed_update(self):
        """Assert that check() operates on pushed updates."""
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        update.pushed = True
        self.db.commit()
        with patch('bodhi.server.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': 'it broke',
                'applicable_policies': ['bodhi-unrestricted'],
            }
            mock_greenwave.return_value = greenwave_response

            result = runner.invoke(check_policies.check, [])

        assert result.exit_code == 0
        update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
        assert update.test_gating_status == models.TestGatingStatus.failed
        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_stable',
            'subject': [{'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                        {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                         'type': 'bodhi_update'}],
            'verbose': False
        }
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)
        # Check for the comment
        expected_comment = "This update's test gating status has been changed to 'failed'."
        assert update.comments[-1].text == expected_comment

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_unrestricted_policy(self):
        """Assert correct behavior when an unrestricted policy is applied"""
        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': True,
                'summary': 'no tests are required',
                'applicable_policies': ['bodhi-unrestricted'],
            }
            mock_greenwave.return_value = greenwave_response
            result = runner.invoke(check_policies.check, [])
            assert result.exit_code == 0
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.ignored
            # Check for the comment
            expected_comment = "This update's test gating status has been changed to 'ignored'."
            assert update.comments[-1].text == expected_comment

        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_stable',
            'subject': [
                {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                 'type': 'bodhi_update'}],
            'verbose': False
        }
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_archived_release_updates(self):
        """Assert that updates for archived releases isn't being considered
        by the script.
        """
        # Archive the F17 release
        rel = self.db.query(models.Release).filter_by(name='F17').one()
        rel.state = models.ReleaseState.archived
        self.db.commit()

        runner = testing.CliRunner()
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.util.greenwave_api_post') as mock_greenwave:
            mock_greenwave.side_effect = Exception(
                'Greenwave should not be accessed for archived releases.')
            result = runner.invoke(check_policies.check, [])
        assert result.exit_code == 0
        assert mock_greenwave.call_count == 0
