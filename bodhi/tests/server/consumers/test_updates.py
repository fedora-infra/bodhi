# Copyright © 2016-2018 Red Hat, Inc. and Caleigh Runge-Hotman
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
"""This test suite contains tests for the bodhi.server.consumers.updates module."""

import copy
import json
import mock
import unittest

import sqlalchemy

from bodhi.server import config, exceptions, models, util
from bodhi.server.consumers import updates
from bodhi.tests.server import base


@mock.patch('bodhi.server.consumers.updates.time.sleep')
class TestUpdatesHandlerConsume(base.BaseTestCase):
    """This test class contains tests for the UpdatesHandler.consume() method."""
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_edited_update_bug_not_in_database(self, work_on_bugs, fetch_test_cases, sleep):
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

        h.consume(message)

        self.assertEqual(work_on_bugs.call_count, 1)
        self.assertTrue(isinstance(work_on_bugs.mock_calls[0][1][0],
                                   sqlalchemy.orm.session.Session))
        self.assertEqual(work_on_bugs.mock_calls[0][1][1].title, u'bodhi-2.0-1.fc17')
        self.assertEqual([b.bug_id for b in work_on_bugs.mock_calls[0][1][2]], [12345, 123456])
        self.assertEqual(fetch_test_cases.call_count, 1)
        self.assertTrue(isinstance(fetch_test_cases.mock_calls[0][1][0],
                                   sqlalchemy.orm.session.Session))
        sleep.assert_called_once_with(1)

        # Inexisting bug with id '123456' should now exists in DB as a bug attached to update
        bug = models.Bug.query.filter_by(bug_id=123456).one()
        update = models.Update.query.filter_by(title=u'bodhi-2.0-1.fc17').one()
        self.assertIn(bug, update.bugs)

    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_edited_update_bug_not_in_update(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Test with a message that indicates that the update is being edited, and the list of bugs
        contains one that UpdatesHandler does not find in the update.
        """
        bug = models.Bug(bug_id=123456)
        self.db.add(bug)
        self.db.commit()
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        message = {
            'topic': 'bodhi.update.edit',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'},
                             'new_bugs': ['12345', '123456']}}}

        h.consume(message)

        self.assertEqual(work_on_bugs.call_count, 1)
        self.assertTrue(isinstance(work_on_bugs.mock_calls[0][1][0],
                                   sqlalchemy.orm.session.Session))
        self.assertEqual(work_on_bugs.mock_calls[0][1][1].title, u'bodhi-2.0-1.fc17')
        self.assertEqual([b.bug_id for b in work_on_bugs.mock_calls[0][1][2]], [12345, 123456])
        self.assertEqual(fetch_test_cases.call_count, 1)
        self.assertTrue(isinstance(fetch_test_cases.mock_calls[0][1][0],
                                   sqlalchemy.orm.session.Session))
        sleep.assert_called_once_with(1)

        # Bug with id '123456' should be attached to update
        bug = models.Bug.query.filter_by(bug_id=123456).one()
        update = models.Update.query.filter_by(title=u'bodhi-2.0-1.fc17').one()
        self.assertIn(bug, update.bugs)

    # We're going to use side effects to mock but still call work_on_bugs and fetch_test_cases so we
    # can ensure that we aren't raising Exceptions from them, while allowing us to only assert that
    # we called them correctly without having to assert all of their behaviors as well.
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases',
                side_effect=updates.UpdatesHandler.fetch_test_cases, autospec=True)
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs',
                side_effect=updates.UpdatesHandler.work_on_bugs, autospec=True)
    def test_edited_update_bugs_in_update(self, work_on_bugs, fetch_test_cases, sleep):
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
        sleep.assert_called_once_with(1)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': False})
    def test_gating_required_false(self, sleep):
        """Assert that test_gating_status is not updated if test_gating is not enabled."""
        update = models.Update.query.filter_by(title=u'bodhi-2.0-1.fc17').one()
        update.test_gating_status = None
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        # Throw a bogus bug id in there to ensure it doesn't raise AssertionError.
        message = {
            'topic': 'bodhi.update.request.testing',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'},
                             'new_bugs': []}}}

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': u'what have you done‽',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [
                    {u'testcase': u'dist.rpmdeplint',
                     u'item': {u'item': u'bodhi-2.0-1.fc17', u'type': u'koji_build'},
                     u'type': u'test-result-missing', u'scenario': None},
                    {u'testcase': u'dist.rpmdeplint',
                     u'item': {u'original_spec_nvr': u'bodhi-2.0-1.fc17'},
                     u'type': u'test-result-missing', u'scenario': None},
                    {u'testcase': u'dist.rpmdeplint',
                     u'item': {u'item': update.alias, u'type': u'bodhi_update'},
                     u'type': u'test-result-missing', u'scenario': None}]}
            mock_greenwave.return_value = greenwave_response

            h.consume(message)

        update = models.Update.query.filter_by(title=u'bodhi-2.0-1.fc17').one()
        self.assertIsNone(update.test_gating_status)
        self.assertIsNone(update.greenwave_summary_string)
        self.assertIsNone(update.greenwave_unsatisfied_requirements)
        sleep.assert_called_once_with(1)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_gating_required_true(self, sleep):
        """Assert that test_gating_status is updated when test_gating is enabled."""
        update = models.Update.query.filter_by(title=u'bodhi-2.0-1.fc17').one()
        update.test_gating_status = None
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        # Throw a bogus bug id in there to ensure it doesn't raise AssertionError.
        message = {
            'topic': 'bodhi.update.request.testing',
            'body': {'msg': {'update': {'alias': u'bodhi-2.0-1.fc17'},
                             'new_bugs': []}}}

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': u'what have you done‽',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [
                    {u'testcase': u'dist.rpmdeplint',
                     u'item': {u'item': u'bodhi-2.0-1.fc17', u'type': u'koji_build'},
                     u'type': u'test-result-missing', u'scenario': None},
                    {u'testcase': u'dist.rpmdeplint',
                     u'item': {u'original_spec_nvr': u'bodhi-2.0-1.fc17'},
                     u'type': u'test-result-missing', u'scenario': None},
                    {u'testcase': u'dist.rpmdeplint',
                     u'item': {u'item': update.alias, u'type': u'bodhi_update'},
                     u'type': u'test-result-missing', u'scenario': None}]}
            mock_greenwave.return_value = greenwave_response

            h.consume(message)

        update = models.Update.query.filter_by(title=u'bodhi-2.0-1.fc17').one()
        self.assertEqual(update.test_gating_status, models.TestGatingStatus.failed)
        self.assertEqual(update.greenwave_summary_string, u'what have you done‽')
        self.assertEqual(update.greenwave_unsatisfied_requirements,
                         json.dumps(greenwave_response['unsatisfied_requirements']))
        sleep.assert_called_once_with(1)

    # We're going to use side effects to mock but still call work_on_bugs and fetch_test_cases so we
    # can ensure that we aren't raising Exceptions from them, while allowing us to only assert that
    # we called them correctly without having to assert all of their behaviors as well.
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases',
                side_effect=updates.UpdatesHandler.fetch_test_cases, autospec=True)
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs',
                side_effect=updates.UpdatesHandler.work_on_bugs, autospec=True)
    def test_request_testing(self, work_on_bugs, fetch_test_cases, sleep):
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
        sleep.assert_called_once_with(1)

    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_unknown_topic(self, work_on_bugs, fetch_test_cases, sleep):
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
        sleep.assert_called_once_with(1)

    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_update_not_found(self, work_on_bugs, fetch_test_cases, sleep):
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

        self.assertEqual(str(exc.exception), "Couldn't find alias 'hurd-1.0-1.fc26' in DB")
        self.assertEqual(work_on_bugs.call_count, 0)
        self.assertEqual(fetch_test_cases.call_count, 0)
        sleep.assert_called_once_with(1)

    @mock.patch('bodhi.server.consumers.updates.log.error')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.consumers.updates.UpdatesHandler.work_on_bugs')
    def test_without_alias(self, work_on_bugs, fetch_test_cases, error, sleep):
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
        sleep.assert_called_once_with(1)


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


class TestUpdatesHandlerWorkOnBugs(base.BaseTestCase):
    """This test class contains tests for the UpdatesHandler.work_on_bugs() method."""

    @mock.patch.dict(config.config, {'bodhi_email': None})
    @mock.patch('bodhi.server.consumers.updates.log.info')
    @mock.patch('bodhi.server.consumers.updates.log.warning')
    def test_bodhi_email_undefined(self, warning, info):
        """work_on_bugs() should log a warning and return if bodhi_email is not defined."""
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)

        # The args don't matter because it should exit before trying to use any of them.
        h.work_on_bugs(None, None, None)

        # We should see warnings about bodhi_email being undefined.
        self.assertEqual(
            warning.mock_calls,
            [mock.call('No bodhi_email defined; not fetching bug details'),
             mock.call('Not configured to handle bugs')])
        # We should not see info calls about syncing bugs, but we should see one about the handler.
        self.assertEqual(
            info.mock_calls,
            [mock.call("Bodhi updates handler listening on:\n"
                       "['topic_prefix.environment.bodhi.update.request.testing',\n "
                       "'topic_prefix.environment.bodhi.update.edit']")])

    def test_security_bug_sets_update_to_security(self):
        """Assert that associating a security bug with an Update changes the Update to security."""
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        update = self.db.query(models.Update).filter(
            models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        # The update should start out in a non-security state so we know that work_on_bugs() changed
        # it.
        self.assertEqual(update.type, models.UpdateType.bugfix)
        bug = models.Bug.query.first()
        # Set this bug to security, so that the update gets switched to security.
        bug.security = True
        self.db.flush()
        bugs = self.db.query(models.Bug).all()

        h.work_on_bugs(h.db_factory, update, bugs)

        self.assertEqual(update.type, models.UpdateType.security)

    @mock.patch('bodhi.server.consumers.updates.log.warning')
    def test_work_on_bugs_exception(self, warning):
        """
        Assert that work_on_bugs logs a warning when an exception is raised.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        h = updates.UpdatesHandler(hub)
        h.db_factory = base.TransactionalSessionMaker(self.Session)

        update = self.db.query(models.Update).filter(
            models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        bugs = self.db.query(models.Bug).all()

        with mock.patch('bodhi.server.consumers.updates.bug_module.bugtracker.getbug',
                        side_effect=RuntimeError("oh no!")):
            h.work_on_bugs(h.db_factory, update, bugs)

        warning.assert_called_once_with('Error occurred during updating single bug', exc_info=True)
