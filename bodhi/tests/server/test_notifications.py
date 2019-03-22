# Copyright 2016-2019 Red Hat, Inc.
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

import json
from unittest import mock

from fedora_messaging import api, testing as fml_testing, exceptions as fml_exceptions

from bodhi.server import notifications, Session, models
from bodhi.tests.server import base


class TestPublish(base.BaseTestCase):
    """Tests for :func:`bodhi.server.notifications.publish`."""

    def test_publish_force(self):
        """Assert that fedora-messaging messages respect the force flag."""
        expected = api.Message(topic='bodhi.demo.topic',
                               body={u'such': 'important'})

        with fml_testing.mock_sends(expected):
            notifications.publish('demo.topic', {'such': 'important'}, force=True)

    def test_publish(self):
        """Assert publish places the message inside the session info dict."""
        notifications.publish('demo.topic', {'such': 'important'})
        session = Session()
        self.assertIn('messages', session.info)
        self.assertEqual(len(session.info['messages']), 1)
        msg = session.info['messages'][0]
        self.assertEqual(msg.topic, 'bodhi.demo.topic')
        self.assertEqual(msg.body, {'such': 'important'})

    def test_publish_sqlalchemy_object(self):
        """Assert publish places the message inside the session info dict."""
        Session.remove()
        expected_msg = {
            u'some_package': {
                u'name': u'so good',
                u'type': 'base',
                u'requirements': None}}
        package = models.Package(name='so good')
        notifications.publish('demo.topic', {'some_package': package})
        session = Session()
        self.assertIn('messages', session.info)
        self.assertEqual(len(session.info['messages']), 1)
        msg = session.info['messages'][0]
        self.assertEqual(msg.body, expected_msg)


class TestSendMessagesAfterCommit(base.BaseTestCase):
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

        self.assertEqual(session.info['messages'], [])

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


class FedMsgEncoderTests(base.BaseTestCase):
    """Tests for the custom JSON encode ``FedMsgEncoder``."""

    def test_default(self):
        """Assert normal types are encoded the same way as the default encoder."""
        self.assertEqual(
            json.dumps('a string'),
            json.dumps('a string', cls=notifications.FedMsgEncoder)
        )

    def test_default_obj_with_json(self):
        """Assert classes with a ``__json__`` function encode as the return of ``__json__``."""

        class JsonClass(object):
            def __json__(self):
                return {'my': 'json'}

        self.assertEqual(
            {'my': 'json'},
            notifications.FedMsgEncoder().default(JsonClass())
        )

    def test_default_other(self):
        """Fallback to the superclasses' default."""
        self.assertRaises(
            TypeError,
            notifications.FedMsgEncoder().default,
            object()
        )
