# Copyright © 2019 Red Hat, Inc. and others.
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

import pytest
from fedora_messaging.api import Message
from fedora_messaging.exceptions import Nack

from bodhi.server import config
from bodhi.server.consumers import Consumer, HandlerInfo, signed


@mock.patch.dict(
    config.config,
    {'pungi.cmd': '/usr/bin/true', 'compose_dir': '/usr/bin/true',
     'compose_stage_dir': '/usr/bin/true'})
class TestConsumer:
    """Test class for the Consumer class."""

    @mock.patch('bodhi.server.consumers.bugs.set_bugtracker')
    @mock.patch('bodhi.server.consumers.buildsys.setup_buildsystem')
    @mock.patch('bodhi.server.consumers.initialize_db')
    @mock.patch('bodhi.server.consumers.log.info')
    def test__init___(self, info, initialize_db, setup_buildsystem, set_bugtracker):
        """Test the __init__() method."""
        consumer = Consumer()

        assert any(x.name == 'Signed' and isinstance(x.handler, signed.SignedHandler)
                   for x in consumer.handler_infos)
        info.assert_called_once_with('Initializing Bodhi')
        initialize_db.assert_called_once_with(config.config)
        setup_buildsystem.assert_called_once_with(config.config)
        set_bugtracker.assert_called_once_with()

    @mock.patch('bodhi.server.consumers.log.exception')
    def test_messaging_callback_exception(self, error):
        """Test catching an exception when processing messages."""
        msg = Message(
            topic="org.fedoraproject.prod.buildsys.tag",
            body={}
        )

        consumer = Consumer()

        with mock.patch.object(
            consumer, 'handler_infos',
            [HandlerInfo('.buildsys.tag', 'Automatic Update', mock.Mock())],
        ) as handler_infos:
            with pytest.raises(Nack) as exc:
                handler_infos[0].handler.side_effect = Exception("Something bad happened")
                consumer(msg)

            logmsg = (f"Something bad happened: Unable to handle message in "
                      f"{consumer.handler_infos[-1].name} handler: {msg}")
            error.assert_called_with(logmsg)

            excmsg = ("Unable to (fully) handle message.\nAffected handlers:\n"
                      + "".join(f"\t{hi.name}: Something bad happened\n"
                                for hi in consumer.handler_infos)
                      + "Message:\n{msg}")

            assert str(exc.value) == excmsg

    @mock.patch('bodhi.server.consumers.AutomaticUpdateHandler')
    @mock.patch('bodhi.server.consumers.SignedHandler')
    def test_messaging_callback_signed_automatic_update(self,
                                                        SignedHandler,
                                                        AutomaticUpdateHandler):
        msg = Message(
            topic="org.fedoraproject.prod.buildsys.tag",
            body={}
        )

        signed_handler = mock.Mock()
        SignedHandler.side_effect = lambda: signed_handler

        automatic_update_handler = mock.Mock()
        AutomaticUpdateHandler.side_effect = lambda: automatic_update_handler

        Consumer()(msg)

        signed_handler.assert_called_once_with(msg)
        automatic_update_handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.ResultsdbHandler')
    def test_messaging_callback_resultsdb(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.resultsdb.result.new",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler
        Consumer()(msg)
        handler.assert_called_once_with(msg)

    @mock.patch('bodhi.server.consumers.WaiverdbHandler')
    def test_messaging_callback_waiverdb(self, Handler):
        msg = Message(
            topic="org.fedoraproject.prod.waiverdb.waiver.new",
            body={}
        )
        handler = mock.Mock()
        Handler.side_effect = lambda: handler
        Consumer()(msg)
        handler.assert_called_once_with(msg)
