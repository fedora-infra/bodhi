# Copyright 2014-2017 Red Hat, Inc.
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
"""A collection of message publishing utilities."""
import logging
import typing

from sqlalchemy import event
from fedora_messaging import api, exceptions as fml_exceptions

from bodhi.server import Session

if typing.TYPE_CHECKING:  # pragma: no cover
    from bodhi.messages.schemas import base  # noqa: 401


_log = logging.getLogger(__name__)


@event.listens_for(Session, 'after_commit')
def send_messages_after_commit(session):
    """
    Send messages via AMQP after a database commit occurs.

    Args:
        session (sqlalchemy.orm.session.Session): The session that was committed.
    """
    if 'messages' in session.info:
        for m in session.info['messages']:
            try:
                api.publish(m)
            except fml_exceptions.BaseException:
                # In the future we should handle errors more gracefully
                _log.exception("An error occurred publishing %r after a database commit", m)
        session.info['messages'] = []


def publish(message: 'base.BodhiMessage', force: bool = False):
    """
    Send a message via Fedora Messaging.

    This is used to send a message to the AMQP broker.

    Args:
        message: The Message you wish to publish.
        force: If False (the default), the message is only sent after the
            currently active database transaction successfully commits. If true,
            the messages is sent immediately.
    """
    if force:
        api.publish(message)
        return

    session = Session()
    if 'messages' not in session.info:
        session.info['messages'] = []
    session.info['messages'].append(message)
    _log.debug('Queuing message %r for delivery on session commit', message.id)
