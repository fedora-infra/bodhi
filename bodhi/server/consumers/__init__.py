# Copyright 2019 Red Hat, Inc.
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
"""
fedora-messaging consumer.

This module is responsible for consuming the messaging from the fedora-messaging bus.
It has the role to inspect the topics of the message and call the correct handler.
"""
from collections import namedtuple
import logging

import fedora_messaging

from bodhi.server import bugs, buildsys, initialize_db
from bodhi.server.config import config
from bodhi.server.consumers.automatic_updates import AutomaticUpdateHandler
from bodhi.server.consumers.signed import SignedHandler
from bodhi.server.consumers.ci import CIHandler
from bodhi.server.consumers.resultsdb import ResultsdbHandler
from bodhi.server.consumers.waiverdb import WaiverdbHandler


log = logging.getLogger('bodhi')


HandlerInfo = namedtuple('HandlerInfo', ['topic_suffix', 'name', 'handler'])


class Consumer:
    """All Bodhi messages are received by this class's __call__() method."""

    def __init__(self):
        """Set up the database, build system, bug tracker, and handlers."""
        log.info('Initializing Bodhi')
        initialize_db(config)
        buildsys.setup_buildsystem(config)
        bugs.set_bugtracker()

        self.handler_infos = [
            HandlerInfo('.buildsys.tag', "Signed", SignedHandler()),
            HandlerInfo('.buildsys.tag', 'Automatic Update', AutomaticUpdateHandler()),
            HandlerInfo('.ci.koji-build.test.running', 'CI', CIHandler()),
            HandlerInfo('.waiverdb.waiver.new', 'WaiverDB', WaiverdbHandler()),
            HandlerInfo('.resultsdb.result.new', 'ResultsDB', ResultsdbHandler()),
        ]

    def __call__(self, msg: fedora_messaging.api.Message):  # noqa: D401
        """
        Callback method called by fedora-messaging consume.

        Redirect messages to the correct handler using the
        message topic.

        Args:
            msg: The message received from the broker.
        """
        log.info(f'Received message from fedora-messaging with topic: {msg.topic}')

        error_handlers_msgs = []

        for handler_info in self.handler_infos:
            if not msg.topic.endswith(handler_info.topic_suffix):
                continue
            log.debug(f'Passing message to the {handler_info.name} handler')
            try:
                handler_info.handler(msg)
            except Exception as e:
                log.exception(f'{str(e)}: Unable to handle message in {handler_info.name} handler: '
                              f'{msg}')
                error_handlers_msgs.append((handler_info.name, str(e)))

        if error_handlers_msgs:
            error_msg = "Unable to (fully) handle message.\nAffected handlers:\n"
            for handler, exc in error_handlers_msgs:
                error_msg += f"\t{handler}: {exc}\n"
            error_msg += "Message:\n{msg}"
            raise fedora_messaging.exceptions.Nack(error_msg)
