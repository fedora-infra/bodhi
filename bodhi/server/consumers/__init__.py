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

from bodhi.server.consumers.composer import ComposerHandler
from bodhi.server.consumers.signed import SignedHandler
from bodhi.server.consumers.updates import UpdatesHandler


log = logging.getLogger('bodhi')


def messaging_callback(msg: fedora_messaging.api.Message):  # noqa: D401
    """
    Callback method called by fedora-messaging consume.

    Redirect messages to the correct handler using the
    message topic.

    Args:
        msg: The message received from the broker.
    """
    log.info(f'Received message from fedora-messaging with topic: {msg.topic}')

    if msg.topic.endswith('.bodhi.composer.start'):
        handler = ComposerHandler()
        log.debug('Passing message to the Composer handler')
        handler(msg)

    if msg.topic.endswith('.buildsys.tag'):
        handler = SignedHandler()
        log.debug('Passing message to the Signed handler')
        handler(msg)

    if msg.topic.endswith('.bodhi.update.request.testing') \
       or msg.topic.endswith('.bodhi.update.edit'):
        handler = UpdatesHandler()
        log.debug('Passing message to the Updates handler')
        handler(msg)
