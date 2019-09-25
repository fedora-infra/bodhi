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

from fedora_messaging.api import Message

from bodhi.server.config import config
from bodhi.server.consumers import signed
from bodhi.server.models import UpdateStatus, TestGatingStatus
from bodhi.tests.server import base


class TestSignedHandlerConsume(base.BasePyTestCase):
    """Test class for the :func:`SignedHandler.consume` method."""

    def setup_method(self, method):
        super().setup_method(method)

        self.sample_message = Message(
            topic='',
            body={
                'build_id': 442562,
                'name': 'colord',
                'tag_id': 214,
                'instance': 's390',
                'tag': 'f26-updates-testing-pending',
                'user': 'sharkcz',
                'version': '1.3.4',
                'owner': 'sharkcz',
                'release': '1.fc26'
            },
        )
        self.sample_side_tag_message = Message(
            topic='',
            body={
                'build_id': 442562,
                'name': 'colord',
                'tag_id': 214,
                'instance': 's390',
                'tag': 'f30-side-tag-testing',
                'user': 'sharkcz',
                'version': '1.3.4',
                'owner': 'sharkcz',
                'release': '1.fc26'
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
    def test_consume_not_pending_testing_tag(self, mock_build_model):
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
        when tag is not correct.
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release = mock.MagicMock()
        update = mock.MagicMock()
        update.from_tag = "f30-side-tag-unknown"
        build.update = update

        self.handler(self.sample_side_tag_message)
        mock_log.info.assert_called_with(
            "Tag is not testing side tag, skipping")
        assert mock_log.info.call_count == 2

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_from_tag_not_signed(self, mock_build_model):
        """
        Assert that update created from tag is not changed to status testing till
        every build is signed when message is received.
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release = mock.MagicMock()
        build.release.get_testing_side_tag.return_value = "f30-side-tag-testing"
        update = mock.MagicMock()
        update.from_tag = "f30-side-tag"
        update.signed.return_value = False
        update.status = UpdateStatus.pending
        build.update = update

        self.handler(self.sample_side_tag_message)
        assert build.signed is True
        assert update.status == UpdateStatus.pending

    @mock.patch('bodhi.server.consumers.signed.Build')
    @mock.patch.dict(config, [('test_gating.required', True)])
    def test_consume_from_tag(self, mock_build_model):
        """
        Assert that update created from tag is handled correctly when message
        is received.
        Update status is changed to testing and corresponding message is sent.
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release = mock.MagicMock()
        build.release.get_testing_side_tag.return_value = "f30-side-tag-testing"
        update = mock.MagicMock()
        update.from_tag = "f30-side-tag"
        update.signed.return_value = True
        update.status = UpdateStatus.pending
        update.release.composed_by_bodhi = False
        update.test_gating_status = None
        build.update = update

        self.handler(self.sample_side_tag_message)
        assert build.signed is True
        assert build.update.request is None
        assert update.status == UpdateStatus.testing
        assert update.test_gating_status == TestGatingStatus.waiting
