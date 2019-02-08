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

from bodhi.server.consumers import signed


class TestSignedHandler___init__(unittest.TestCase):
    """This test class contains tests for the SignedHandler.__init__() method."""
    def test___init__(self):
        """Test __init__() with a manufactured hub config."""
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment', 'topic_prefix': 'topic_prefix'}

        handler = signed.SignedHandler(hub)

        self.assertEqual(handler.topic, ['topic_prefix.environment.buildsys.tag'])

    @mock.patch('bodhi.server.consumers.signed.fedmsg.consumers.FedmsgConsumer.__init__')
    def test_calls_super(self, __init__):
        """Assert that __init__() calls the superclass __init__()."""
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment', 'topic_prefix': 'topic_prefix'}

        handler = signed.SignedHandler(hub)

        self.assertEqual(handler.topic, ['topic_prefix.environment.buildsys.tag'])
        __init__.assert_called_once_with(hub)


class TestSignedHandlerConsume(unittest.TestCase):
    """Test class for the :func:`SignedHandler.consume` method."""

    def setUp(self):
        self.sample_message = {
            'body': {
                'i': 628,
                'timestamp': 1484692585,
                'msg_id': '2017-821031da-be3a-4f4b-91df-0baa834ca8a4',
                'crypto': 'x509',
                'topic': 'org.fedoraproject.prod.buildsys.tag',
                'signature': '100% real please trust me',
                'msg': {
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
            },
        }
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment', 'topic_prefix': 'topic_prefix'}
        self.handler = signed.SignedHandler(hub)

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume(self, mock_build_model):
        """Assert that messages marking the build as signed updates the database"""
        build = mock_build_model.get.return_value
        build.release.pending_testing_tag = self.sample_message['body']['msg']['tag']

        self.handler.consume(self.sample_message)
        self.assertTrue(build.signed is True)

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_not_pending_testing_tag(self, mock_build_model):
        """
        Assert that messages whose tag don't match the pending testing tag don't update the DB
        """
        build = mock_build_model.get.return_value
        build.release.pending_testing_tag = "some tag that isn't pending testing"

        self.handler.consume(self.sample_message)
        self.assertFalse(build.signed is True)

    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_no_release(self, mock_build_model):
        """
        Assert that messages about builds that haven't been assigned a release don't update the DB
        """
        build = mock_build_model.get.return_value
        build.release = None

        self.handler.consume(self.sample_message)
        self.assertFalse(build.signed is True)

    @mock.patch('bodhi.server.consumers.signed.log')
    @mock.patch('bodhi.server.consumers.signed.Build')
    def test_consume_no_build(self, mock_build_model, mock_log):
        """Assert that messages referencing builds Bodhi doesn't know about don't update the DB"""
        mock_build_model.get.return_value = None

        self.handler.consume(self.sample_message)
        mock_log.info.assert_called_with('Build was not submitted, skipping')
