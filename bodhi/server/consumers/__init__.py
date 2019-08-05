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
import logging

import fedora_messaging

from bodhi.server import bugs, buildsys, initialize_db
from bodhi.server.config import config
from bodhi.server.consumers.automatic_updates import AutomaticUpdateHandler
from bodhi.server.consumers.signed import SignedHandler
from bodhi.server.consumers.greenwave import GreenwaveHandler


log = logging.getLogger('bodhi')


class Consumer:
    """All Bodhi messages are received by this class's __call__() method."""

    def __init__(self):
        """Set up the database, build system, bug tracker, and handlers."""
        log.info('Initializing Bodhi')
        initialize_db(config)
        buildsys.setup_buildsystem(config)
        bugs.set_bugtracker()

        self.automatic_update_handler = AutomaticUpdateHandler()
        self.signed_handler = SignedHandler()
        self.greenwave_handler = GreenwaveHandler()

    def __call__(self, msg: fedora_messaging.api.Message):  # noqa: D401
        """
        Callback method called by fedora-messaging consume.

        Redirect messages to the correct handler using the
        message topic.

        Args:
            msg: The message received from the broker.
        """
        log.info(f'Received message from fedora-messaging with topic: {msg.topic}')

        try:
            if msg.topic.endswith('.buildsys.tag'):
                log.debug('Passing message to the Signed handler')
                self.signed_handler(msg)

                log.debug('Passing message to the Automatic Update handler')
                self.automatic_update_handler(msg)

            if msg.topic.endswith('.greenwave.decision.update'):
                log.debug('Passing message to the Greenwave handler')
                self.greenwave_handler(msg)
        except Exception as e:
            error_msg = f'{str(e)}: Unable to handle message: {msg}'
            log.exception(error_msg)
            raise fedora_messaging.exceptions.Nack(error_msg)
