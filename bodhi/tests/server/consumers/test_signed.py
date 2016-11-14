# -*- coding: utf-8 -*-

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

import unittest

import mock

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
