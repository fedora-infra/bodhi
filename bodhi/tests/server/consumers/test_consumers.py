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

from bodhi.server import config
from bodhi.server.consumers import composer, Consumer, signed, updates
from bodhi.tests.server import base


@mock.patch.dict(
    config.config,
    {'pungi.cmd': '/usr/bin/true', 'compose_dir': '/usr/bin/true',
     'compose_stage_dir': '/usr/bin/true'})
class TestConsumer(base.BaseTestCase):
    """Test class for the Consumer class."""

    @mock.patch('bodhi.server.consumers.bugs.set_bugtracker')
    @mock.patch('bodhi.server.consumers.buildsys.setup_buildsystem')
    @mock.patch('bodhi.server.consumers.initialize_db')
    @mock.patch('bodhi.server.consumers.log.info')
    def test__init__(self, info, initialize_db, setup_buildsystem, set_bugtracker):
        """Test the __init__() method."""
        consumer = Consumer()

        self.assertTrue(isinstance(consumer.composer_handler, composer.ComposerHandler))
        self.assertTrue(isinstance(consumer.signed_handler, signed.SignedHandler))
        self.assertTrue(isinstance(consumer.updates_handler, updates.UpdatesHandler))
        info.assert_called_once_with('Initializing Bodhi')
        initialize_db.assert_called_once_with(config.config)
        setup_buildsystem.assert_called_once_with(config.config)
        set_bugtracker.assert_called_once_with()

    @mock.patch('bodhi.server.consumers.ComposerHandler')
    def test_messaging_callback_composer(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.bodhi.composer.start",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler

        Consumer()(msg)

        handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.SignedHandler')
    def test_messaging_callback_signed(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.buildsys.tag",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler

        Consumer()(msg)

        handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.UpdatesHandler')
    def test_messaging_callback_updates_testing(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.bodhi.update.request.testing",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler

        Consumer()(msg)

        handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.UpdatesHandler')
    def test_messaging_callback_updates_edit(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.bodhi.update.edit",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler

        Consumer()(msg)

        handler.assert_called_once_with(msg)
