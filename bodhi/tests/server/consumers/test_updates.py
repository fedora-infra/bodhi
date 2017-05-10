# -*- coding: utf-8 -*-

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
"""This test suite contains tests for the bodhi.server.consumers.updates module."""

import copy
import unittest

import mock
import sqlalchemy

from bodhi.server import exceptions, models, util
from bodhi.server.consumers import updates
from bodhi.tests.server import base


class TestUpdatesHandlerConsume(base.BaseTestCase):
    """This test class contains tests for the UpdatesHandler.consume() method."""
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_edited_update_bug_not_in_update(self, work_on_bugs, fetch_test_cases):
        """
        Test with a message that indicates that the update is being edited, and the list of bugs
        contains one that UpdatesHandler does not find in the database.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        message = {
            'topic': 'bodhi.update.edit',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'},
                             'new_bugs': ['12345', '123456']}}}

        self.assertRaises(AssertionError, h.consume, message)

        self.assertEqual(work_on_bugs.call_count, 0)
        self.assertEqual(fetch_test_cases.call_count, 0)

    # We're going to use side effects to mock but still call work_on_bugs and fetch_test_cases so we
    # can ensure that we aren't raising Exceptions from them, while allowing us to only assert that
    # we called them correctly without having to assert all of their behaviors as well.
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases',
                side_effect=updates.UpdatesHandler.fetch_test_cases, autospec=True)
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs',
                side_effect=updates.UpdatesHandler.work_on_bugs, autospec=True)
    def test_edited_update_bugs_in_update(self, work_on_bugs, fetch_test_cases):
        """
        Test with a message that indicates that the update is being edited, and the list of bugs
        matches what UpdatesHandler finds in the database.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        message = {
            'topic': 'bodhi.update.edit',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'},
                             'new_bugs': ['12345']}}}

        h.consume(message)

        self.assertEqual(work_on_bugs.call_count, 1)
        self.assertTrue(isinstance(work_on_bugs.mock_calls[0][1][1],
                                   sqlalchemy.orm.session.Session))
        self.assertEqual(work_on_bugs.mock_calls[0][1][2].title, u'bodhi-2.0-1.fc17')
        self.assertEqual([b.bug_id for b in work_on_bugs.mock_calls[0][1][3]], [12345])
        self.assertEqual(fetch_test_cases.call_count, 1)
        self.assertTrue(isinstance(fetch_test_cases.mock_calls[0][1][1],
                                   sqlalchemy.orm.session.Session))

    # We're going to use side effects to mock but still call work_on_bugs and fetch_test_cases so we
    # can ensure that we aren't raising Exceptions from them, while allowing us to only assert that
    # we called them correctly without having to assert all of their behaviors as well.
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases',
                side_effect=updates.UpdatesHandler.fetch_test_cases, autospec=True)
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs',
                side_effect=updates.UpdatesHandler.work_on_bugs, autospec=True)
    def test_request_testing(self, work_on_bugs, fetch_test_cases):
        """
        Assert correct behavior when the message tells us that the update is requested for testing.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        # Throw a bogus bug id in there to ensure it doesn't raise AssertionError.
        message = {
            'topic': 'bodhi.update.request.testing',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'},
                             'new_bugs': ['this isnt a real bug lol']}}}

        h.consume(message)

        self.assertEqual(work_on_bugs.call_count, 1)
        self.assertTrue(isinstance(work_on_bugs.mock_calls[0][1][1],
                                   sqlalchemy.orm.session.Session))
        self.assertEqual(work_on_bugs.mock_calls[0][1][2].title, u'bodhi-2.0-1.fc17')
        # Despite our weird bogus bug id, the update's bug list should have been used.
        self.assertEqual([b.bug_id for b in work_on_bugs.mock_calls[0][1][3]], [12345])
        self.assertEqual(fetch_test_cases.call_count, 1)
        self.assertTrue(isinstance(fetch_test_cases.mock_calls[0][1][1],
                                   sqlalchemy.orm.session.Session))

    @mock.patch('bodhi.server.buildsys.DevBuildsys.getTaskRequest', side_effect=IOError("oh no"))
    def test_scm_url_fail(self, getTaskRequest):
        """Test that the scm_url is added when communication with Koji fails."""
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        message = {
            'topic': 'bodhi.update.request.testing',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'}}}}

        h.consume(message)

        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        # Since we could not communicate with Koji, the scm_url should still be None.
        self.assertEqual(b.scm_url, None)
        getTaskRequest.assert_called_once_with(127621)

    @mock.patch('bodhi.server.models.Build.get_scm_url')
    def test_scm_url_present(self, get_scm_url):
        """Test that the scm_url is left alone when it's already set in the database."""
        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        b.scm_url = u'git://some.cool.host/rpms/neat#master'
        self.db.commit()
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        message = {
            'topic': 'bodhi.update.request.testing',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'}}}}

        h.consume(message)

        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        # Since the scm_url was already set on the build, it shouldn't have changed and we shouldn't
        # have asked koji about it.
        self.assertEqual(b.scm_url, 'git://some.cool.host/rpms/neat#master')
        self.assertEqual(get_scm_url.call_count, 0)

    def test_scm_url_success(self):
        """Test that the scm_url is added when communication with Koji is successful."""
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        message = {
            'topic': 'bodhi.update.request.testing',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'}}}}

        h.consume(message)

        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        # The scm_url should be set to the value from the DevBuildsys fake call.
        self.assertEqual(
            b.scm_url,
            'git://pkgs.fedoraproject.org/rpms/bodhi?#2e994ca8b3296e62e8b0aadee1c5c0649559625a')

    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_unknown_topic(self, work_on_bugs, fetch_test_cases):
        """
        Assert that NotImplementedError gets raised when an unknown topic is received.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        # Use a bogus topic to trigger the NotImplementedError.
        message = {
            'topic': 'bodhi.update.nawjustkiddin',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'},
                             'new_bugs': ['12345']}}}

        self.assertRaises(NotImplementedError, h.consume, message)

        self.assertEqual(work_on_bugs.call_count, 0)
        self.assertEqual(fetch_test_cases.call_count, 0)

    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_update_not_found(self, work_on_bugs, fetch_test_cases):
        """
        If the message references an update that isn't found, assert that an Exception is raised.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        # Use a bogus topic to trigger the NotImplementedError.
        message = {
            'topic': 'bodhi.update.request.testing',
            'body': {'msg': {'update': {'alias': u'hurd-1.0-1.fc26'}}}}

        with self.assertRaises(exceptions.BodhiException) as exc:
            h.consume(message)

        self.assertEqual(str(exc.exception), "Couldn't find alias u'hurd-1.0-1.fc26' in DB")
        self.assertEqual(work_on_bugs.call_count, 0)
        self.assertEqual(fetch_test_cases.call_count, 0)

    @mock.patch('bodhi.server.consumers.updates.log.error')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_without_alias(self, work_on_bugs, fetch_test_cases, error):
        """
        An error should get logged and the function should return if the message has no alias.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        message = {
            'topic': 'bodhi.update.edit',
            'body': {'msg': {'update': {},
                             'new_bugs': ['12345']}}}

        h.consume(message)

        self.assertEqual(work_on_bugs.call_count, 0)
        self.assertEqual(fetch_test_cases.call_count, 0)
        error.assert_called_once_with(
            "Update Handler got update with no alias {'new_bugs': ['12345'], 'update': {}}.")


class TestUpdatesHandlerInit(unittest.TestCase):
    """This test class contains tests for the UpdatesHandler.__init__() method."""
    def test_handle_bugs_bodhi_email_falsy(self):
        """
        Assert that bug handling is disabled when bodhi_email is configured "falsy".
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}

        with mock.patch.dict(updates.config, {'bodhi_email': ''}):
            h = updates.UpdatesHandler(hub)

        self.assertEqual(h.handle_bugs, False)

    def test_handle_bugs_bodhi_email_missing(self):
        """
        Assert that bug handling is disabled when bodhi_email is not configured.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        replacement_config = copy.deepcopy(updates.config)
        del replacement_config['bodhi_email']

        with mock.patch.dict(updates.config, replacement_config, clear=True):
            h = updates.UpdatesHandler(hub)

        self.assertEqual(h.handle_bugs, False)

    @mock.patch('bodhi.server.consumers.updates.fedmsg.consumers.FedmsgConsumer.__init__')
    def test_super___init___called(self, __init__):
        """
        Make sure the superclass's __init__() was called.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}

        with mock.patch.dict(updates.config, {'bodhi_email': 'bowlofeggs@fpo.org'}):
            updates.UpdatesHandler(hub)

        __init__.assert_called_once_with(hub)

    @mock.patch('bodhi.server.consumers.updates.bug_module.set_bugtracker')
    def test_typical_config(self, set_bugtracker):
        """
        Test the method with a typical config.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}

        with mock.patch.dict(updates.config, {'bodhi_email': 'bowlofeggs@fpo.org'}):
            h = updates.UpdatesHandler(hub)

        self.assertEqual(h.handle_bugs, True)
        self.assertEqual(type(h.db_factory), util.TransactionalSessionMaker)
        self.assertEqual(
            h.topic,
            ['topic_prefix.environment.bodhi.update.request.testing',
             'topic_prefix.environment.bodhi.update.edit'])
        set_bugtracker.assert_called_once_with()
