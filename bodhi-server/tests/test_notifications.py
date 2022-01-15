# Copyright 2016-2019 Red Hat, Inc. and others.
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
"""This test module contains tests for bodhi.server.notifications."""

from unittest import mock

from fedora_messaging import api, testing as fml_testing, exceptions as fml_exceptions

from bodhi.messages.schemas import compose as compose_schemas
from bodhi.server import notifications, Session
from . import base


class TestPublish(base.BasePyTestCase):
    """Tests for :func:`bodhi.server.notifications.publish`."""

    def test_publish_force(self):
        """Assert that fedora-messaging messages respect the force flag."""
        message = compose_schemas.ComposeSyncWaitV1.from_dict({'agent': 'double O seven',
                                                               'repo': 'f30'})
        with fml_testing.mock_sends(message):
            notifications.publish(message, force=True)

    def test_publish(self):
        """Assert publish places the message inside the session info dict."""
        message = compose_schemas.ComposeSyncWaitV1.from_dict({'agent': 'double O seven',
                                                               'repo': 'f30'})

        notifications.publish(message)

        session = Session()
        assert 'messages' in session.info
        assert len(session.info['messages']) == 1
        msg = session.info['messages'][0]
        assert msg == message

    def test_publish_sqlalchemy_object(self):
        """Assert publish places the message inside the session info dict."""
        message = compose_schemas.ComposeSyncWaitV1.from_dict({'agent': 'double O seven',
                                                               'repo': 'f30'})
        Session.remove()

        notifications.publish(message)

        session = Session()
        assert 'messages' in session.info
        assert len(session.info['messages']) == 1
        msg = session.info['messages'][0]
        assert msg == message


class TestSendMessagesAfterCommit(base.BasePyTestCase):
    """Tests for :func:`bodhi.server.notifications.send_messages_after_commit`."""

    def test_no_messages(self):
        """Assert if no messages have been queued, the event handler succeeds."""
        with fml_testing.mock_sends():
            notifications.send_messages_after_commit(Session())

    def test_clear_messages_on_send(self):
        """Assert the message queue is cleared after the event handler runs."""
        session = Session()
        session.info['messages'] = [api.Message()]

        with fml_testing.mock_sends(api.Message()):
            notifications.send_messages_after_commit(session)

        assert session.info['messages'] == []

    @mock.patch('bodhi.server.notifications.api.publish')
    @mock.patch('bodhi.server.notifications._log')
    def test_error_logged(self, mock_log, mock_pub):
        session = Session()
        message = api.Message()
        session.info['messages'] = [message]
        mock_pub.side_effect = fml_exceptions.BaseException()

        notifications.send_messages_after_commit(session)

        mock_log.exception.assert_called_once_with(
            "An error occurred publishing %r after a database commit", message)
