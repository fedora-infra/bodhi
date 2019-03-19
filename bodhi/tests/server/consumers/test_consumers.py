# Copyright © 2019 Red Hat, Inc.
#
# This file is part of Bodhi.
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
"""Test the bodhi.server.consumers package."""
from unittest import mock

from fedora_messaging.api import Message

from bodhi.tests.server import base
from bodhi.server.consumers import messaging_callback


class TestConsumers(base.BaseTestCase):
    """Test class for the messaging_callback function """

    @mock.patch('bodhi.server.consumers.ComposerHandler')
    def test_messaging_callback_composer(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.bodhi.composer.start",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler
        messaging_callback(msg)
        handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.SignedHandler')
    def test_messaging_callback_signed(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.buildsys.tag",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler
        messaging_callback(msg)
        handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.UpdatesHandler')
    def test_messaging_callback_updates_testing(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.bodhi.update.request.testing",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler
        messaging_callback(msg)
        handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.UpdatesHandler')
    def test_messaging_callback_updates_edit(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.bodhi.update.edit",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler
        messaging_callback(msg)
        handler.assert_called_once_with(msg)
