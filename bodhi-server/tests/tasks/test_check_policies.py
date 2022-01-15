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
"""This module contains tests for the bodhi.server.tasks.check_policies module."""

from unittest.mock import patch, call
import datetime

from bodhi.server import models
from bodhi.server.tasks import check_policies_task
from bodhi.server.tasks.check_policies import main as check_policies_main
from bodhi.server.config import config
from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.bugs")
    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.check_policies.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys, bugs):
        check_policies_task()
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        bugs.set_bugtracker.assert_called_with()
        main_function.assert_called_with()


class TestCheckPolicies(BaseTaskTestCase):
    """This class contains tests for the check_policies() function."""

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_satisfied(self):
        """Assert correct behavior when the policies enforced by Greenwave are satisfied"""
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        update.critpath = True
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_responses = [
                {
                    'policies_satisfied': True,
                    'summary': 'All required tests passed',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements',
                        'bodhiupdate_bodhipush_openqa'
                    ],
                    'satisfied_requirements': [
                        {
                            'result_id': 39603316,
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-passed'
                        },
                    ],
                    'unsatisfied_requirements': []
                },
                {
                    'policies_satisfied': True,
                    'summary': 'no tests are required',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [],
                }
            ]
            mock_greenwave.side_effect = greenwave_responses
            check_policies_main()
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.passed

        expected_queries = [
            {
                'product_version': 'fedora-17', 'decision_context': context,
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                     'type': 'bodhi_update'}],
                'verbose': False
            } for context in ('bodhi_update_push_stable_critpath', 'bodhi_update_push_stable')
        ]
        expected_calls = [
            call(config['greenwave_api_url'] + '/decision', query) for query in expected_queries
        ]
        assert mock_greenwave.call_args_list == expected_calls

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_pending_satisfied(self):
        """Assert that Updates whose status is pending are checked against
        greenwave with the ``bodhi_update_push_testing`` decision context. """
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.pending
        update.critpath = True
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_responses = [
                {
                    'policies_satisfied': True,
                    'summary': 'All required tests passed',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements',
                        'bodhiupdate_bodhipush_openqa'
                    ],
                    'satisfied_requirements': [
                        {
                            'result_id': 39603316,
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-passed'
                        },
                    ],
                    'unsatisfied_requirements': []
                },
                {
                    'policies_satisfied': True,
                    'summary': 'no tests are required',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [],
                }
            ]
            mock_greenwave.side_effect = greenwave_responses
            check_policies_main()
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.passed

        expected_queries = [
            {
                'product_version': 'fedora-17',
                'decision_context': context,
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                     'type': 'bodhi_update'}],
                'verbose': False,
            } for context in ('bodhi_update_push_testing_critpath', 'bodhi_update_push_testing')
        ]
        expected_calls = [
            call(config['greenwave_api_url'] + '/decision', query) for query in expected_queries
        ]
        assert mock_greenwave.call_args_list == expected_calls

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_unsatisfied_waiting(self):
        """Assert correct behavior when the policies enforced by Greenwave are unsatisfied:
        results missing, no failures, less than two hours since update creation results
        in 'waiting' status.
        """
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        update.critpath = True
        # Clear pending messages
        self.db.info['messages'] = []
        update.date_submitted = datetime.datetime.utcnow()
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            item = 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year)
            greenwave_responses = [
                {
                    'policies_satisfied': False,
                    'summary': '2 of 2 required test results missing',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements',
                        'bodhiupdate_bodhipush_openqa'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [
                        {
                            'item': {
                                'item': item,
                                'type': 'bodhi_update'
                            },
                            'scenario': 'fedora.updates-everything-boot-iso.x86_64.64bit',
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-missing'
                        },
                        {
                            'item': {
                                'item': item,
                                'type': 'bodhi_update'
                            },
                            'scenario': 'fedora.updates-everything-boot-iso.x86_64.uefi',
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-missing'
                        },
                    ]
                },
                {
                    'policies_satisfied': True,
                    'summary': 'no tests are required',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [],
                }
            ]
            mock_greenwave.side_effect = greenwave_responses
            check_policies_main()
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.waiting
            # Check for the comment
            expected_comment = "This update's test gating status has been changed to 'waiting'."
            assert update.comments[-1].text == expected_comment

        expected_queries = [
            {
                'product_version': 'fedora-17', 'decision_context': context,
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                     'type': 'bodhi_update'}],
                'verbose': False
            } for context in ('bodhi_update_push_stable_critpath', 'bodhi_update_push_stable')
        ]
        expected_calls = [
            call(config['greenwave_api_url'] + '/decision', query) for query in expected_queries
        ]
        assert mock_greenwave.call_args_list == expected_calls

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_unsatisfied_waiting_too_long(self):
        """Assert correct behavior when the policies enforced by Greenwave are unsatisfied:
        results missing, no failures, more than two hours since update modification results
        in 'failed' status.
        """
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        update.critpath = True
        # Clear pending messages
        self.db.info['messages'] = []
        update.date_submitted = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            item = 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year)
            greenwave_responses = [
                {
                    'policies_satisfied': False,
                    'summary': '2 of 2 required test results missing',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements',
                        'bodhiupdate_bodhipush_openqa'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [
                        {
                            'item': {
                                'item': item,
                                'type': 'bodhi_update'
                            },
                            'scenario': 'fedora.updates-everything-boot-iso.x86_64.64bit',
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-missing'
                        },
                        {
                            'item': {
                                'item': item,
                                'type': 'bodhi_update'
                            },
                            'scenario': 'fedora.updates-everything-boot-iso.x86_64.uefi',
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-missing'
                        },
                    ]
                },
                {
                    'policies_satisfied': True,
                    'summary': 'no tests are required',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [],
                }
            ]
            mock_greenwave.side_effect = greenwave_responses
            check_policies_main()
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.failed
            # Check for the comment
            expected_comment = "This update's test gating status has been changed to 'failed'."
            assert update.comments[-1].text == expected_comment

        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_stable_critpath',
            'subject': [
                {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                 'type': 'bodhi_update'}],
            'verbose': False
        }
        # we only expect *one* call here because the *first* query
        # (on the _critpath context) should be enough to conclude the
        # status is failed: it would be wrong to needlessly run the
        # second query. note the mock responses are in the order we
        # expect the queries to be run, critpath first
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_policies_unsatisfied_failed(self):
        """Assert correct behavior when the policies enforced by Greenwave are unsatisfied:
        failed tests always means failed status. This also tests that we behave correctly
        even if the *first* query shows requirements satisfied, but the *second* query has
        failed required tests.
        """
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        update.critpath = True
        update.date_submitted = datetime.datetime.utcnow()
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            # here, we're mocking the scenario from
            # https://pagure.io/fedora-ci/general/issue/263 , where
            # openQA tests passed, but a package in the update had a
            # local gating config that only specified the context
            # bodhi_update_push_stable (not _push_stable_critpath),
            # and a test specified in that local policy failed
            greenwave_responses = [
                {
                    'policies_satisfied': True,
                    'summary': 'All required tests passed',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements',
                        'bodhiupdate_bodhipush_openqa'
                    ],
                    'satisfied_requirements': [
                        {
                            'result_id': 39603316,
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-passed'
                        },
                    ],
                    'unsatisfied_requirements': []
                },
                {
                    'policies_satisfied': False,
                    'summary': '1 of 1 required tests failed',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [
                        {
                            'item': {
                                'item': 'bodhi-2.0-1.fc17',
                                'type': 'koji_build'
                            },
                            'scenario': None,
                            'subject_type': 'koji_build',
                            'testcase': 'fedora-ci.koji-build.tier0.functional',
                            'type': 'test-result-failed'
                        },
                    ],
                }
            ]
            mock_greenwave.side_effect = greenwave_responses
            check_policies_main()
            update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
            assert update.test_gating_status == models.TestGatingStatus.failed
            # Check for the comment
            expected_comment = "This update's test gating status has been changed to 'failed'."
            assert update.comments[-1].text == expected_comment

        expected_queries = [
            {
                'product_version': 'fedora-17', 'decision_context': context,
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                     'type': 'bodhi_update'}],
                'verbose': False
            } for context in ('bodhi_update_push_stable_critpath', 'bodhi_update_push_stable')
        ]
        expected_calls = [
            call(config['greenwave_api_url'] + '/decision', query) for query in expected_queries
        ]
        assert mock_greenwave.call_args_list == expected_calls

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_no_policies_enforced(self):
        """
        Assert correct behavior when policies are not enforced.

        When test gating is disabled, each Update's test_gating_status will be None.
        """
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        update.test_gating_status = None
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            mock_greenwave.return_value = RuntimeError('The error was blablabla')

            check_policies_main()

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
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        update.critpath = True
        update.pushed = True
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            item = 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year)
            greenwave_responses = [
                {
                    'policies_satisfied': False,
                    'summary': '1 of 2 required tests failed, 1 result missing',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements',
                        'bodhiupdate_bodhipush_openqa'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [
                        {
                            'item': {
                                'item': item,
                                'type': 'bodhi_update'
                            },
                            'scenario': 'fedora.updates-everything-boot-iso.x86_64.64bit',
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-failed'
                        },
                        {
                            'item': {
                                'item': item,
                                'type': 'bodhi_update'
                            },
                            'scenario': 'fedora.updates-everything-boot-iso.x86_64.uefi',
                            'subject_type': 'bodhi_update',
                            'testcase': 'update.install_default_update_netinst',
                            'type': 'test-result-missing'
                        },
                    ]
                },
                {
                    'policies_satisfied': True,
                    'summary': 'no tests are required',
                    'applicable_policies': [
                        'kojibuild_bodhipush_no_requirements',
                        'kojibuild_bodhipush_remoterule',
                        'bodhiupdate_bodhipush_no_requirements'
                    ],
                    'satisfied_requirements': [],
                    'unsatisfied_requirements': [],
                }
            ]
            mock_greenwave.side_effect = greenwave_responses

            check_policies_main()

        update = self.db.query(models.Update).filter(models.Update.id == update.id).one()
        assert update.test_gating_status == models.TestGatingStatus.failed
        expected_query = {
            'product_version': 'fedora-17', 'decision_context': 'bodhi_update_push_stable_critpath',
            'subject': [{'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                        {'item': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                         'type': 'bodhi_update'}],
            'verbose': False
        }
        # we only expect *one* call here, as with the earlier
        # 'failed' test
        mock_greenwave.assert_called_once_with(config['greenwave_api_url'] + '/decision',
                                               expected_query)
        # Check for the comment
        expected_comment = "This update's test gating status has been changed to 'failed'."
        assert update.comments[-1].text == expected_comment

    @patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_unrestricted_policy(self):
        """Assert correct behavior when an unrestricted policy is applied"""
        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': True,
                'summary': 'no tests are required',
                'applicable_policies': [
                    'kojibuild_bodhipush_no_requirements',
                    'kojibuild_bodhipush_remoterule',
                    'bodhiupdate_bodhipush_no_requirements'
                ],
                'satisfied_requirements': [],
                'unsatisfied_requirements': [],
            }
            mock_greenwave.return_value = greenwave_response
            check_policies_main()
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

        update = self.db.query(models.Update).all()[0]
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()
        with patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            mock_greenwave.side_effect = Exception(
                'Greenwave should not be accessed for archived releases.')
            check_policies_main()

        assert mock_greenwave.call_count == 0
