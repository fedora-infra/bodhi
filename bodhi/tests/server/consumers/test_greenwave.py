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
"""This test suite contains tests for the bodhi.server.consumers.greenwave module."""

from unittest import mock

from fedora_messaging.api import Message

from bodhi.server import models
from bodhi.server.consumers import greenwave
from bodhi.server.config import config
from bodhi.tests.server import create_update
from bodhi.tests.server.base import BasePyTestCase, TransactionalSessionMaker


class TestGreenwaveHandler(BasePyTestCase):
    """Test class for the :func:`GreenwaveHandler` method."""

    def setup_method(self, method):
        super(TestGreenwaveHandler, self).setup_method(method)
        self.sample_message = Message(
            topic="org.fedoraproject.prod.greenwave.decision.update",
            body={
                "subject_identifier": "bodhi-2.0-1.fc17",
                "subject_type": "koji_build",
                'policies_satisfied': True,
                'summary': "all tests have passed",
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
        )
        self.handler = greenwave.GreenwaveHandler()
        self.handler.db_factory = TransactionalSessionMaker(self.Session)
        self.single_build_update = self.db.query(models.Update).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()

    def test_single_build(self):
        """
        Assert that a greenwave message updates the gating status of an update.
        """
        update = self.single_build_update

        # before the greenwave consumer run the gating tests status is None
        assert update.test_gating_status is None

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            self.handler(self.sample_message)
            # Only one build, the info should come from the message and not the greenwave API
            assert mock_greenwave.called is False

        # After the consumer run the gating tests status was updated.
        assert update.test_gating_status == models.TestGatingStatus.passed

    def test_single_build_failed(self):
        """
        Assert that a greenwave message updates the gating status of an update when gating status is
        failed.
        """
        update = self.single_build_update

        self.sample_message.body["policies_satisfied"] = False
        self.sample_message.body["summary"] = "1 of 1 required tests failed"
        self.sample_message.body["satisfied_requirements"] = []
        self.sample_message.body["unsatisfied_requirements"] = [
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
        self.handler(self.sample_message)
        assert update.test_gating_status == models.TestGatingStatus.failed

    def test_single_build_ignored(self):
        """
        Assert that a greenwave message updates the gating status of an update when gating status is
        ignored.
        """
        update = self.single_build_update

        self.sample_message.body["policies_satisfied"] = True
        self.sample_message.body["summary"] = "no tests are required"
        self.sample_message.body["satisfied_requirements"] = []
        self.sample_message.body["unsatisfied_requirements"] = []
        self.handler(self.sample_message)
        assert update.test_gating_status == models.TestGatingStatus.ignored

    @mock.patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_multiple_builds(self):
        """
        Assert that a greenwave message updates the gating tests status of an update.
        """
        # Create an update with multiple builds
        with mock.patch(target='uuid.uuid4', return_value='multiplebuilds'):
            update = create_update(
                self.db, ['MultipleBuild1-1.0-1.fc17', 'MultipleBuild2-1.0-1.fc17']
            )
            update.type = models.UpdateType.bugfix
            update.severity = models.UpdateSeverity.medium
        self.db.flush()

        # Reference it in the incoming message
        self.sample_message.body["subject_identifier"] = "MultipleBuild1-1.0-1.fc17"

        # Put bogus info in the message to make sure it does not get used
        self.sample_message.body["policies_satisfied"] = False
        self.sample_message.body["summary"] = "this should not be used"

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
            self.handler(self.sample_message)

        # After the consumer run the gating tests status was updated.
        assert update.test_gating_status == models.TestGatingStatus.passed

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_bad_message(self, mock_log):
        """ Assert that the consumer ignores messages badly formed """
        bad_message = Message(topic="", body={})
        self.handler(bad_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Ignoring message without body.")

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_message_missing_subject_identifier(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        subject_identifier in the message
        """
        bad_message = Message(topic="", body={"foo": "bar"})
        self.handler(bad_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Couldn't find subject_identifier in Greenwave message")

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_message_missing_policies_satisfied(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        policies_satisfied in the message
        """
        bad_message = Message(topic="", body={"subject_identifier": "foobar"})
        self.handler(bad_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Couldn't find policies_satisfied in Greenwave message")

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_wrong_build_nvr(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        subject_identifier (build nvr) in the DB.
        """
        self.sample_message.body["subject_identifier"] = "notapackage-2.0-1.fc17"
        self.handler(self.sample_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Couldn't find build notapackage-2.0-1.fc17 in DB")

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_compose_subject_type(self, mock_log):
        """ Assert that the consumer ignores messages with subject_type equal to compose """
        self.sample_message.body["subject_type"] = "compose"
        self.handler(self.sample_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Not requesting a decision for a compose")
