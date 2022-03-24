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
"""This test suite contains tests for the bodhi.server.consumers.waiverdb module."""

from unittest import mock

from fedora_messaging.api import Message

from bodhi.server import models
from bodhi.server.consumers import waiverdb

from ..base import BasePyTestCase, TransactionalSessionMaker


class TestWaiverdbHandler(BasePyTestCase):
    """Test class for the :func:`WaiverdbHandler` method."""

    def setup_method(self, method):
        super(TestWaiverdbHandler, self).setup_method(method)
        self.handler = waiverdb.WaiverdbHandler()
        self.handler.db_factory = TransactionalSessionMaker(self.Session)
        self.single_build_update = self.db.query(models.Update).join(models.Build).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()

    def get_sample_message(self, typ="bodhi_update"):
        """Returns a sample message for the specified type."""
        if typ == "bodhi_update":
            item = self.single_build_update.alias
        elif typ == "koji_build":
            item = self.single_build_update.builds[0].nvr
        return Message(
            topic="org.fedoraproject.prod.waiverdb.waiver.new",
            body={
                "subject_type": typ,
                "subject": {
                    "item": item,
                    "type": typ
                }
            }
        )

    def test_waiverdb_koji_waiver(self):
        """
        Assert that a Koji build waiver message updates the gating
        status of the update, unless it's in passed status.
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
            testmsg = self.get_sample_message(typ="koji_build")
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

    def test_waiverdb_bodhi_waiver(self):
        """
        Assert that a Bodhi update waiver message updates the gating
        status of the update.
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
            testmsg = self.get_sample_message(typ="bodhi_update")
            self.handler(testmsg)
            assert update.test_gating_status == models.TestGatingStatus.passed
            # don't bother testing every other path here too

    @mock.patch('bodhi.server.consumers.waiverdb.log')
    def test_waiverdb_bad_message(self, mock_log):
        """ Assert that the consumer ignores badly formed messages."""
        bad_message = Message(topic="", body={})
        self.handler(bad_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Ignoring message without body.")

    @mock.patch('bodhi.server.consumers.waiverdb.log')
    def test_waiverdb_message_missing_subject(self, mock_log):
        """
        Assert that the consumer logs and returns if we could not find the
        subject in the message.
        """
        bad_message = Message(topic="", body={"foo": "bar"})
        self.handler(bad_message)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(
            f"Couldn't find subject in WaiverDB message {bad_message.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_waiverdb_message_missing_subject_type(self, mock_log):
        """
        Assert that the consumer logs and returns if we could not find the
        subject type in the message.
        """
        bad_message = Message(topic="", body={"subject": {"foo": "bar"}})
        self.handler(bad_message)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(
            f"Couldn't find item type in message {bad_message.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_waiverdb_message_irrelevant_result_type(self, mock_log):
        """
        Assert that the consumer logs and returns if the result type
        is not a relevant one.
        """
        bad_message = Message(topic="", body={"subject": {"type": "foo"}})
        self.handler(bad_message)
        assert mock_log.debug.call_count == 1
        mock_log.debug.assert_called_with("Irrelevant item type foo")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_waiverdb_koji_message_no_nvr(self, mock_log):
        """
        Assert that the consumer logs and returns if a Koji waiver
        message is missing the NVR.
        """
        testmsg = self.get_sample_message(typ="koji_build")
        del testmsg.body["subject"]["item"]
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(f"Couldn't find nvr in message {testmsg.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_waiverdb_koji_message_wrong_build_nvr(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        build nvr in the DB.
        """
        testmsg = self.get_sample_message(typ="koji_build")
        testmsg.body["subject"]["item"] = "notapackage-2.0-1.fc17"
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with("Couldn't find build notapackage-2.0-1.fc17 in DB")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_waiverdb_bodhi_message_no_updateid(self, mock_log):
        """
        Assert that the consumer logs and returns if a Bodhi waiver
        message is missing the update ID.
        """
        testmsg = self.get_sample_message(typ="bodhi_update")
        del testmsg.body["subject"]["item"]
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with(f"Couldn't find update ID in message {testmsg.id}")

    @mock.patch('bodhi.server.consumers.util.log')
    def test_waiverdb_bodhi_message_wrong_updateid(self, mock_log):
        """
        Assert that the consumer raise an exception if we could not find the
        update ID in the DB.
        """
        testmsg = self.get_sample_message(typ="bodhi_update")
        testmsg.body["subject"]["item"] = "NOTANUPDATE"
        self.handler(testmsg)
        assert mock_log.error.call_count == 1
        mock_log.error.assert_called_with("Couldn't find update NOTANUPDATE in DB")
