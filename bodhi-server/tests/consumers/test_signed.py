# Copyright © 2016-2019 Red Hat, Inc.
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
"""This test suite contains tests for the bodhi.server.consumers.signed module."""

from unittest import mock

from fedora_messaging import api
from fedora_messaging import testing as fml_testing

from bodhi.messages.schemas import update as update_schemas
from bodhi.server.config import config
from bodhi.server.consumers import signed
from bodhi.server.models import (
    Build,
    TestGatingStatus,
    Update,
    UpdateRequest,
    UpdateStatus,
)

from .. import base


class TestSignedHandlerConsume(base.BasePyTestCase):
    """Test class for the :func:`SignedHandler.consume` method."""

    def setup_method(self, method):
        super().setup_method(method)

        self.sample_message = api.Message(
            topic='',
            body={
                'build_id': 442562,
                'name': 'bodhi',
                'tag_id': 214,
                'instance': 's390',
                'tag': 'f26-updates-testing-pending',
                'user': 'sharkcz',
                'version': '2.0',
                'owner': 'sharkcz',
                'release': '1.fc17'
            },
        )
        self.sample_side_tag_message = api.Message(
            topic='',
            body={
                'build_id': 442562,
                'name': 'bodhi',
                'tag_id': 214,
                'instance': 's390',
                'tag': 'f30-side-tag-testing-pending',
                'user': 'sharkcz',
                'version': '2.0',
                'owner': 'sharkcz',
                'release': '1.fc17'
            },
        )
        self.sample_side_tag_message_2 = api.Message(
            topic='',
            body={
                'build_id': 442562,
                'name': 'bodhi',
                'tag_id': 214,
                'instance': 's390',
                'tag': 'f30-testing-pending',
                'user': 'sharkcz',
                'version': '2.0',
                'owner': 'sharkcz',
                'release': '1.fc17'
            },
        )
        self.handler = signed.SignedHandler()

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume(self, mock_build_model):
        """Assert that messages marking the build as signed updates the database"""
        build = mock_build_model.get.return_value
        build.signed = False
        update = mock.MagicMock()
        update.from_tag = None
        build.update = update
        build.release.pending_testing_tag = self.sample_message.body["tag"]

        self.handler(self.sample_message)
        assert build.signed is True

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_build_with_no_update(self, mock_build_model):
        """Assert that messages marking the build as signed updates the database"""
        build = mock_build_model.get.return_value
        build.signed = False
        build.update = None
        build.release.pending_testing_tag = self.sample_message.body["tag"]

        self.handler(self.sample_message)
        assert build.signed is True

    @mock.patch('bodhi.server.consumers.signed.log')
    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_not_pending_testing_tag(self, mock_build_model, mock_log):
        """
        Assert that messages whose tag don't match the pending testing tag don't update the DB
        """
        build = mock_build_model.get.return_value
        build.signed = False
        update = mock.MagicMock()
        update.from_tag = None
        build.update = update
        build.release.pending_testing_tag = "some tag that isn't pending testing"

        self.handler(self.sample_message)
        mock_log.info.assert_called_with(
            "Tag is not pending_testing tag, skipping")
        assert mock_log.info.call_count == 2
        assert build.signed is False

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_no_release(self, mock_build_model):
        """
        Assert that messages about builds that haven't been assigned a release don't update the DB
        """
        build = mock_build_model.get.return_value
        build.signed = False
        update = mock.MagicMock()
        update.from_tag = None
        build.update = update
        build.release = None

        self.handler(self.sample_message)
        assert build.signed is False

    @mock.patch('bodhi.server.consumers.signed.log')
    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_no_build(self, mock_build_model, mock_log):
        """Assert that messages referencing builds Bodhi doesn't know about don't update the DB"""
        mock_build_model.get.return_value = None

        self.handler(self.sample_message)
        mock_log.info.assert_called_with('Build was not submitted, skipping')

    @mock.patch('bodhi.server.consumers.signed.log')
    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_duplicate(self, mock_build_model, mock_log):
        """Assert that the handler is idempotent."""
        build = mock_build_model.get.return_value
        build.release.pending_testing_tag = self.sample_message.body["tag"]
        build.signed = True
        update = mock.MagicMock()
        update.from_tag = None
        build.update = update

        self.handler(self.sample_message)
        mock_log.info.assert_called_with(
            "Build was already marked as signed (maybe a duplicate message)")
        assert mock_log.info.call_count == 2

    @mock.patch('bodhi.server.consumers.signed.log')
    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_from_tag_wrong_tag(self, mock_build_model, mock_log):
        """
        Assert that messages about builds from side tag updates are skipped
        when tag is not correct (rawhide).
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release = mock.MagicMock()
        update = mock.MagicMock()
        update.from_tag = "f30-side-tag-unknown"
        update.release.composed_by_bodhi = False
        build.update = update

        self.handler(self.sample_side_tag_message)
        mock_log.info.assert_called_with(
            "Tag is not testing side tag, skipping")
        assert mock_log.info.call_count == 2

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_from_tag_build_signed(self, mock_build_model):
        """
        Assert that messages about builds from side tag updates coming from
        normal releases are marked as signed.
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release = mock.MagicMock()
        build.release.pending_testing_tag = "f30-testing-pending"
        update = mock.MagicMock()
        update.from_tag = "f30-side-tag"
        update.release.composed_by_bodhi = True
        build.update = update

        self.handler(self.sample_side_tag_message_2)
        assert build.signed == True

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_from_tag_not_signed(self, mock_build_model):
        """
        Assert that update created from tag is not changed to status testing till
        every build is signed when message is received.
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release = mock.MagicMock()
        build.release.get_pending_testing_side_tag.return_value = "f30-side-tag-testing-pending"
        update = mock.MagicMock()
        update.release.composed_by_bodhi = False
        update.from_tag = "f30-side-tag"
        update.signed = False
        update.status = UpdateStatus.pending
        build.update = update

        self.handler(self.sample_side_tag_message)
        assert build.signed is True
        assert update.status == UpdateStatus.pending

    @mock.patch.dict(config, [('test_gating.required', True)])
    def test_consume_from_tag(self):
        """
        Assert that update created from tag is handled correctly when message
        is received.
        Update status is changed to testing and corresponding message is sent.
        """
        self.handler.db_factory = base.TransactionalSessionMaker(self.Session)
        update = self.db.query(Update).join(Build).filter(Build.nvr == 'bodhi-2.0-1.fc17').one()
        update.from_tag = "f30-side-tag"
        update.status = UpdateStatus.pending
        update.release.composed_by_bodhi = False
        update.builds[0].signed = False
        update.pushed = False

        self.db.commit()
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
            with fml_testing.mock_sends(update_schemas.UpdateReadyForTestingV2):
                self.handler(self.sample_side_tag_message)

        assert update.builds[0].signed is True
        assert update.builds[0].update.request is None
        assert update.status == UpdateStatus.testing
        assert update.pushed is True
        assert update.test_gating_status == TestGatingStatus.passed

    @mock.patch.dict(config, [('test_gating.required', True)])
    @mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
    @mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
    @mock.patch('bodhi.server.models.Update.add_tag')
    def test_consume_from_tag_composed_by_bodhi(self, add_tag):
        """
        Assert that update created from tag for a release composed by bodhi
        is handled correctly when message is received.
        The update request should be set to 'testing' so that the next composer run
        will change the update status.
        """
        self.handler.db_factory = base.TransactionalSessionMaker(self.Session)
        update = self.db.query(Update).join(Build).filter(Build.nvr == 'bodhi-2.0-1.fc17').one()
        update.from_tag = "f30-side-tag"
        update.status = UpdateStatus.pending
        update.request = None
        update.release.composed_by_bodhi = True
        update.release.pending_testing_tag = "f30-testing-pending"
        update.builds[0].signed = False
        update.pushed = False

        self.db.commit()
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
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                self.handler(self.sample_side_tag_message_2)

        assert update.builds[0].signed is True
        assert update.builds[0].update.request == UpdateRequest.testing
        assert update.status == UpdateStatus.pending
        assert update.pushed is False
        assert update.test_gating_status == TestGatingStatus.passed
        assert add_tag.not_called()
