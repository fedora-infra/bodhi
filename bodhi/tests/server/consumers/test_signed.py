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
import unittest

from fedora_messaging.api import Message

from bodhi.server.consumers import signed


class TestSignedHandlerConsume(unittest.TestCase):
    """Test class for the :func:`SignedHandler.consume` method."""

    def setUp(self):
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
        self.handler = signed.SignedHandler()

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume(self, mock_build_model):
        """Assert that messages marking the build as signed updates the database"""
        build = mock_build_model.get.return_value
        build.signed = False
        build.release.pending_testing_tag = self.sample_message.body["tag"]

        self.handler(self.sample_message)
        self.assertTrue(build.signed is True)

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_not_pending_testing_tag(self, mock_build_model):
        """
        Assert that messages whose tag don't match the pending testing tag don't update the DB
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release.pending_testing_tag = "some tag that isn't pending testing"

        self.handler(self.sample_message)
        self.assertFalse(build.signed is True)

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_no_release(self, mock_build_model):
        """
        Assert that messages about builds that haven't been assigned a release don't update the DB
        """
        build = mock_build_model.get.return_value
        build.signed = False
        build.release = None

        self.handler(self.sample_message)
        self.assertFalse(build.signed is True)

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

        self.handler(self.sample_message)
        mock_log.info.assert_called_with(
            "Build was already marked as signed (maybe a duplicate message)")
        self.assertEqual(mock_log.info.call_count, 2)
