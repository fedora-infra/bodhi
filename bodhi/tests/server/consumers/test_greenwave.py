# Copyright © 2019 Red Hat, Inc.
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
from bodhi.tests.server.base import BaseTestCase, TransactionalSessionMaker


class TestGreenwaveHandler(BaseTestCase):
    """Test class for the :func:`GreenwaveHandler` method."""

    def setUp(self):
        super().setUp()
        self.sample_message = Message(
            topic="org.fedoraproject.prod.greenwave.decision.update",
            body={"subject_identifier": "bodhi-2.0-1.fc17", "subject_type": "koji_build"},
        )
        self.handler = greenwave.GreenwaveHandler()

    @mock.patch.dict(config, [('greenwave_api_url', 'http://domain.local')])
    def test_update_test_gating_status(self):
        """
        Assert that a greenwave message updates the gating tests status of an update.
        """

        self.handler.db_factory = TransactionalSessionMaker(self.Session)
        update = self.db.query(models.Update).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()

        # before the greenwave consumer run the gating tests status is None
        assert update.test_gating_status is None

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': True,
                'summary': "all tests have passed"
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
        self.assertEqual(mock_log.debug.call_count, 1)
        mock_log.debug.assert_called_with("Ignoring message without body.")

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_message_missing_info(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        subject_identifier in the message
        """

        bad_message = Message(topic="", body={"msg": {}})
        self.handler(bad_message)
        self.assertEqual(mock_log.debug.call_count, 1)
        mock_log.debug.assert_called_with("Couldn't find subject_identifier in Greenwave message")

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_wrong_build_nvr(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        subject_identifier (build nvr) in the DB.
        """
        self.handler.db_factory = TransactionalSessionMaker(self.Session)
        self.sample_message.body["subject_identifier"] = "notapackage-2.0-1.fc17"
        self.handler(self.sample_message)
        self.assertEqual(mock_log.debug.call_count, 1)
        mock_log.debug.assert_called_with("Couldn't find build notapackage-2.0-1.fc17 in DB")

    @mock.patch('bodhi.server.consumers.greenwave.log')
    def test_greenwave_compose_subject_type(self, mock_log):
        """ Assert that the consumer ignores messages with subject_type equal to compose """

        self.sample_message.body["subject_type"] = "compose"
        self.handler(self.sample_message)
        self.assertEqual(mock_log.debug.call_count, 1)
        mock_log.debug.assert_called_with("Not requesting a decision for a compose")
