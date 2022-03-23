# Copyright © 2019 Red Hat, Inc. and others.
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
"""This test suite contains tests for the bodhi.server.consumers.resultsdb module."""

from unittest import mock

from fedora_messaging.api import Message

from bodhi.server import models
from bodhi.server.consumers import resultsdb

from ..base import BasePyTestCase, TransactionalSessionMaker


class TestResultsdbHandler(BasePyTestCase):
    """Test class for the :func:`ResultsdbHandler` method."""

    def setup_method(self, method):
        super(TestResultsdbHandler, self).setup_method(method)
        self.handler = resultsdb.ResultsdbHandler()
        self.handler.db_factory = TransactionalSessionMaker(self.Session)
        self.single_build_update = self.db.query(models.Update).join(models.Build).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()

    def get_sample_message(self, typ="bodhi_update", passed=True):
        """
        Returns a sample message, for the specified type and success
        status.
        """
        outcome = "PASSED"
        if not passed:
            outcome = "FAILED"
        if typ == "bodhi_update":
            data = {"item": [self.single_build_update.alias], "type": ["bodhi_update"]}
        elif typ == "koji_build":
            nvr = self.single_build_update.builds[0].nvr
            data = {"nvr": [nvr], "item": [nvr], "type": ["koji_build"]}
        return Message(
            topic="org.fedoraproject.prod.resultsdb.result.new",
            body={
                "outcome": outcome,
                "data": data
            }
        )

    def test_resultsdb_passed_koji_test(self):
        """
        Assert that a passed test ResultsDB message for a Koji build
        from an update updates the gating status of the update if in
        failed or waiting status, or with no status.
        """
        update = self.single_build_update

        # before the greenwave consumer run the gating tests status is None
        assert update.test_gating_status is None

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': True,
                'summary': "All required tests passed",
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
            }
            mock_greenwave.return_value = greenwave_response
            testmsg = self.get_sample_message(typ="koji_build", passed=True)
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.passed
            # now check failed
            update.test_gating_status = models.TestGatingStatus.failed
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.passed
            # and waiting
            update.test_gating_status = models.TestGatingStatus.waiting
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.passed
            # now check we don't update if already passed
            with mock.patch("bodhi.server.models.Update.update_test_gating_status") as updmock:
                self.handler(testmsg)
                assert updmock.call_count == 0

    def test_resultsdb_failed_koji_test(self):
        """
        Assert that a failed test ResultsDB message for a Koji build
        from an update updates the gating status of the update if in
        passed or waiting status, or with no status.
        """
        update = self.single_build_update

        # before the consumer run the gating tests status is None
        assert update.test_gating_status is None

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': "1 of 1 required tests failed",
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
                            'type': 'bodhi_update'
                        },
                        'scenario': 'fedora.updates-everything-boot-iso.x86_64.64bit',
                        'subject_type': 'bodhi_update',
                        'testcase': 'update.install_default_update_netinst',
                        'type': 'test-result-failed'
                    }
                ]
            }
            mock_greenwave.return_value = greenwave_response
            testmsg = self.get_sample_message(typ="koji_build", passed=False)
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.failed
            # now check failed
            update.test_gating_status = models.TestGatingStatus.failed
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.failed
            # and waiting
            update.test_gating_status = models.TestGatingStatus.waiting
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.failed
            # now check we don't update if already failed
            with mock.patch("bodhi.server.models.Update.update_test_gating_status") as updmock:
                self.handler(testmsg)
                assert updmock.call_count == 0

    def test_resultsdb_bodhi_tests(self):
        """
        Assert that ResultsDB messages for tests on an update result in
        the gating status of that update being updated.
        """
        update = self.single_build_update

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': True,
                'summary': "All required tests passed",
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
            }
            mock_greenwave.return_value = greenwave_response
            # check the 'success' case
            testmsg = self.get_sample_message(typ="bodhi_update", passed=True)
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.passed
            # now check the 'failure' case
            testmsg = self.get_sample_message(typ="bodhi_update", passed=False)
            greenwave_response = {
                'policies_satisfied': False,
                'summary': "1 of 1 required tests failed",
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
                            'type': 'bodhi_update'
                        },
                        'scenario': 'fedora.updates-everything-boot-iso.x86_64.64bit',
                        'subject_type': 'bodhi_update',
                        'testcase': 'update.install_default_update_netinst',
                        'type': 'test-result-failed'
                    }
                ]
            }
            mock_greenwave.return_value = greenwave_response
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.failed

    @mock.patch('bodhi.server.consumers.resultsdb.log')
    def test_resultsdb_bad_message(self, mock_log):
        """ Assert that the consumer ignores badly formed messages."""
        bad_message = Message(topic="", body={})
        self.handler(bad_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Ignoring message without body.")

    @mock.patch('bodhi.server.consumers.resultsdb.log')
    def test_resultsdb_message_missing_data(self, mock_log):
        """
        Assert that the consumer logs and returns if we could not find the
        data dict in the message.
        """
        bad_message = Message(topic="", body={"foo": "bar"})
        self.handler(bad_message)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(
            f"Couldn't find data dict in ResultsDB message {bad_message.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_resultsdb_message_missing_result_type(self, mock_log):
        """
        Assert that the consumer logs and returns if we could not find the
        result type in the message.
        """
        bad_message = Message(topic="", body={"data": {"foo": "bar"}})
        self.handler(bad_message)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(
            f"Couldn't find item type in message {bad_message.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_resultsdb_message_irrelevant_result_type(self, mock_log):
        """
        Assert that the consumer logs and returns if the result type
        is not a relevant one.
        """
        bad_message = Message(topic="", body={"data": {"type": "foo"}})
        self.handler(bad_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Irrelevant item type foo")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_resultsdb_koji_message_no_nvr(self, mock_log):
        """
        Assert that the consumer logs and returns if a Koji result
        message is missing the NVR.
        """
        testmsg = self.get_sample_message(typ="koji_build", passed=True)
        del testmsg.body["data"]["nvr"]
        del testmsg.body["data"]["item"]
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(f"Couldn't find nvr in message {testmsg.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_resultsdb_koji_message_wrong_build_nvr(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        build nvr in the DB.
        """
        testmsg = self.get_sample_message(typ="koji_build", passed=True)
        testmsg.body["data"]["nvr"] = ["notapackage-2.0-1.fc17"]
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with("Couldn't find build notapackage-2.0-1.fc17 in DB")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_resultsdb_bodhi_message_no_updateid(self, mock_log):
        """
        Assert that the consumer logs and returns if a Bodhi result
        message is missing the update ID.
        """
        testmsg = self.get_sample_message(typ="bodhi_update", passed=True)
        del testmsg.body["data"]["item"]
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(f"Couldn't find update ID in message {testmsg.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_resultsdb_bodhi_message_wrong_updateid(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        update ID in the DB.
        """
        testmsg = self.get_sample_message(typ="bodhi_update", passed=True)
        testmsg.body["data"]["item"] = ["NOTANUPDATE"]
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with("Couldn't find update NOTANUPDATE in DB")
