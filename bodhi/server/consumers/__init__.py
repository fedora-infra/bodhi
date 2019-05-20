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
try:
    from bodhi.server.consumers.composer import ComposerHandler
except ImportError:  # pragma: no cover
    # If the composer isn't installed, it's OK, we just won't be able to process composer.start
    # messages.
    ComposerHandler = None  # pragma: no cover
from bodhi.server.consumers.signed import SignedHandler
from bodhi.server.consumers.updates import UpdatesHandler


log = logging.getLogger('bodhi')


class Consumer:
    """All Bodhi messages are received by this class's __call__() method."""

    def __init__(self):
        """Set up the database, build system, bug tracker, and handlers."""
        log.info('Initializing Bodhi')
        initialize_db(config)
        buildsys.setup_buildsystem(config)
        bugs.set_bugtracker()

        if ComposerHandler:
            self.composer_handler = ComposerHandler()
        else:
            log.info('The composer is not installed - Bodhi will ignore composer.start messages.')
            self.composer_handler = None
        self.signed_handler = SignedHandler()
        self.updates_handler = UpdatesHandler()

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
            if msg.topic.endswith('.bodhi.composer.start'):
                if self.composer_handler:
                    log.debug('Passing message to the Composer handler')
                    self.composer_handler(msg)
                else:
                    raise ValueError('Unable to process composer.start message topics because the '
                                     'Composer is not installed')

            if msg.topic.endswith('.buildsys.tag'):
                log.debug('Passing message to the Signed handler')
                self.signed_handler(msg)

            if msg.topic.endswith('.bodhi.update.request.testing') \
               or msg.topic.endswith('.bodhi.update.edit'):
                log.debug('Passing message to the Updates handler')
                self.updates_handler(msg)
        except Exception as e:
            error_msg = f'{str(e)}: Unable to handle message: {msg}'
            log.exception(error_msg)
            raise fedora_messaging.exceptions.Nack(error_msg)
