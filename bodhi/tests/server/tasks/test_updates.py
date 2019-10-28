# Copyright © 2016-2019 Red Hat, Inc. and Caleigh Runge-Hottman
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
"""This test suite contains tests for the bodhi.server.tasks.updates module."""

from unittest import mock
import copy
from urllib.error import URLError

import pytest
import sqlalchemy
from fedora_messaging import testing as fml_testing

from bodhi.messages.schemas import update as update_schemas
from bodhi.server import config, exceptions, models, util
from bodhi.server.tasks import handle_update, updates
from bodhi.tests.server import base


class TestTask:
    @mock.patch("bodhi.server.tasks.bugs")
    @mock.patch("bodhi.server.tasks.buildsys")
    @mock.patch("bodhi.server.tasks.initialize_db")
    @mock.patch("bodhi.server.tasks.config")
    @mock.patch("bodhi.server.tasks.updates.UpdatesHandler")
    def test_task(self, handler_class, config_mock, init_db_mock, buildsys, bugs):
        handler = mock.Mock()
        handler_class.side_effect = lambda: handler
        handle_update(api_version=42, foo="bar")
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        bugs.set_bugtracker.assert_called_with()
        handler.run.assert_called_with(api_version=42, data={"foo": "bar"})


@mock.patch('bodhi.server.tasks.updates.time.sleep')
class TestUpdatesHandlerConsume(base.BasePyTestCase):
    """This test class contains tests for the UpdatesHandler.consume() method."""
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs')
    def test_edited_update_bug_not_in_database(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Test an update edition when the list of bugs contains one that
        UpdatesHandler does not find in the database.
        """
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        h.run(
            api_version=1,
            data={
                'action': 'edit',
                'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                           'user': {'name': 'brodhi'}, 'status': 'pending', 'request': 'testing'},
                'new_bugs': [12345, 123456]})

        assert work_on_bugs.call_count == 1
        assert isinstance(work_on_bugs.mock_calls[0][1][0], sqlalchemy.orm.session.Session)
        assert work_on_bugs.mock_calls[0][1][1].title == 'bodhi-2.0-1.fc17'
        assert [b.bug_id for b in work_on_bugs.mock_calls[0][1][2]] == [12345, 123456]
        assert fetch_test_cases.call_count == 1
        assert isinstance(fetch_test_cases.mock_calls[0][1][0], sqlalchemy.orm.session.Session)
        sleep.assert_called_once_with(1)

        # Nonexistent bug with id '123456' should now exist in DB as a bug attached to update
        bug = models.Bug.query.filter_by(bug_id=123456).one()
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert bug in update.bugs

    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs')
    def test_edited_update_bug_not_in_update(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Test an update edition when the list of bugs contains one that
        UpdatesHandler does not find in the update.
        """
        bug = models.Bug(bug_id=123456)
        self.db.add(bug)
        self.db.commit()

        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        h.run(
            api_version=1,
            data={
                'action': 'edit',
                'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                           'user': {'name': 'brodhi'}, 'status': str(update.status),
                           'request': str(update.request)},
                'new_bugs': [12345, 123456]})

        assert work_on_bugs.call_count == 1
        assert isinstance(work_on_bugs.mock_calls[0][1][0], sqlalchemy.orm.session.Session)
        assert work_on_bugs.mock_calls[0][1][1].title == 'bodhi-2.0-1.fc17'
        assert [b.bug_id for b in work_on_bugs.mock_calls[0][1][2]] == [12345, 123456]
        assert fetch_test_cases.call_count == 1
        assert isinstance(fetch_test_cases.mock_calls[0][1][0], sqlalchemy.orm.session.Session)
        sleep.assert_called_once_with(1)

        # Bug with id '123456' should be attached to update
        bug = models.Bug.query.filter_by(bug_id=123456).one()
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert bug in update.bugs

    # We're going to use side effects to mock but still call work_on_bugs and fetch_test_cases so we
    # can ensure that we aren't raising Exceptions from them, while allowing us to only assert that
    # we called them correctly without having to assert all of their behaviors as well.
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases',
                side_effect=updates.UpdatesHandler.fetch_test_cases, autospec=True)
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs',
                side_effect=updates.UpdatesHandler.work_on_bugs, autospec=True)
    def test_edited_update_bugs_in_update(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Test with a message that indicates that the update is being edited, and the list of bugs
        matches what UpdatesHandler finds in the database.
        """
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        h.run(
            api_version=1,
            data={
                'action': 'edit',
                'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                           'user': {'name': 'brodhi'}, 'status': str(update.status),
                           'request': str(update.request)},
                'new_bugs': [12345]})

        assert work_on_bugs.call_count == 1
        assert isinstance(work_on_bugs.mock_calls[0][1][1], sqlalchemy.orm.session.Session)
        assert work_on_bugs.mock_calls[0][1][2].title == 'bodhi-2.0-1.fc17'
        assert [b.bug_id for b in work_on_bugs.mock_calls[0][1][3]] == [12345]
        assert fetch_test_cases.call_count == 1
        assert isinstance(fetch_test_cases.mock_calls[0][1][1], sqlalchemy.orm.session.Session)
        sleep.assert_called_once_with(1)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': False})
    def test_gating_required_false(self, sleep):
        """Assert that test_gating_status is not updated if test_gating is not enabled."""
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.test_gating_status = None

        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': 'what have you done‽',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                     'type': 'test-result-missing', 'scenario': None},
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': update.alias, 'type': 'bodhi_update'},
                     'type': 'test-result-missing', 'scenario': None}]}
            mock_greenwave.return_value = greenwave_response

            h.run(
                api_version=1,
                data={
                    'action': 'testing',
                    'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                               'user': {'name': 'brodhi'}, 'status': str(update.status),
                               'request': str(update.request)},
                    'new_bugs': []})

        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert update.test_gating_status is None
        sleep.assert_called_once_with(1)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_gating_required_true(self, sleep):
        """Assert that test_gating_status is updated when test_gating is enabled."""
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.test_gating_status = None

        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': 'what have you done‽',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                     'type': 'test-result-missing', 'scenario': None},
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': update.alias, 'type': 'bodhi_update'},
                     'type': 'test-result-missing', 'scenario': None}]}
            mock_greenwave.return_value = greenwave_response

            h.run(
                api_version=1,
                data={
                    'action': 'testing',
                    'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                               'user': {'name': 'brodhi'}, 'status': str(update.status),
                               'request': str(update.request)},
                    'new_bugs': []})

        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert update.test_gating_status == models.TestGatingStatus.failed
        sleep.assert_called_once_with(1)

    # We're going to use side effects to mock but still call work_on_bugs and fetch_test_cases so we
    # can ensure that we aren't raising Exceptions from them, while allowing us to only assert that
    # we called them correctly without having to assert all of their behaviors as well.
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases',
                side_effect=updates.UpdatesHandler.fetch_test_cases, autospec=True)
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs',
                side_effect=updates.UpdatesHandler.work_on_bugs, autospec=True)
    def test_request_testing(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Assert correct behavior when the message tells us that the update is requested for testing.
        """
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        h.run(
            api_version=1,
            data={
                'action': 'testing',
                'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                           'user': {'name': 'brodhi'}, 'status': str(update.status),
                           'request': str(update.request)}})

        assert work_on_bugs.call_count == 1
        assert isinstance(work_on_bugs.mock_calls[0][1][1], sqlalchemy.orm.session.Session)
        assert work_on_bugs.mock_calls[0][1][2].title == 'bodhi-2.0-1.fc17'
        # The update's bug list should have been used.
        assert [b.bug_id for b in work_on_bugs.mock_calls[0][1][3]] == [12345]
        assert fetch_test_cases.call_count == 1
        assert isinstance(fetch_test_cases.mock_calls[0][1][1], sqlalchemy.orm.session.Session)
        sleep.assert_called_once_with(1)

    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs')
    def test_unknown_topic(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Assert that NotImplementedError gets raised when an unknown action is received.
        """
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        # Use a bogus action to trigger the NotImplementedError.
        pytest.raises(
            NotImplementedError, h.run,
            api_version=1,
            data={
                'action': 'update.nawjustkiddin',
                'update': {'alias': update.alias},
                'new_bugs': [12345]})

        assert work_on_bugs.call_count == 0
        assert fetch_test_cases.call_count == 0
        sleep.assert_called_once_with(1)

    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs')
    def test_update_not_found(self, work_on_bugs, fetch_test_cases, sleep):
        """
        If the message references an update that isn't found, assert that an Exception is raised.
        """
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        with pytest.raises(exceptions.BodhiException) as exc:
            h.run(
                api_version=1,
                data={
                    'action': 'testing',
                    'update': {'alias': 'does not exist', 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                               'user': {'name': 'brodhi'}, 'status': 'pending',
                               'request': 'testing'}})

        assert str(exc.value) == "Couldn't find alias 'does not exist' in DB"
        assert work_on_bugs.call_count == 0
        assert fetch_test_cases.call_count == 0
        sleep.assert_called_once_with(1)

    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs')
    @mock.patch.dict(config.config, [('test_gating.required', True)])
    def test_rawhide_update_edit_move_to_testing(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Assert that a pending rawhide update that was edited gets moved to testing
        if all the builds in the update are signed.
        """
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.status = models.UpdateStatus.pending
        update.release.composed_by_bodhi = False
        update.builds[0].signed = True

        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        with fml_testing.mock_sends(update_schemas.UpdateReadyForTestingV1):
            with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
                greenwave_response = {
                    'policies_satisfied': False,
                    'summary': 'what have you done‽',
                    'applicable_policies': ['taskotron_release_critical_tasks'],
                    'unsatisfied_requirements': [
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                         'type': 'test-result-missing', 'scenario': None},
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': update.alias, 'type': 'bodhi_update'},
                         'type': 'test-result-missing', 'scenario': None}]}
                mock_greenwave.return_value = greenwave_response
                h.run(api_version=1,
                      data={
                          'action': 'edit',
                          'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                                     'user': {'name': 'bodhi'}, 'status': str(update.status),
                                     'request': str(update.request)}, 'new_bugs': []})

        assert update.status == models.UpdateStatus.testing
        assert update.test_gating_status == models.TestGatingStatus.failed

    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs')
    def test_rawhide_update_edit_stays_pending(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Assert that a pending rawhide update that was edited does not get moved to testing
        if not all the builds in the update are signed.
        """
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.status = models.UpdateStatus.pending
        update.release.composed_by_bodhi = False
        update.builds[0].signed = False

        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        h.run(api_version=1,
              data={
                  'action': 'edit',
                  'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                             'user': {'name': 'bodhi'}, 'status': str(update.status),
                             'request': str(update.request)}, 'new_bugs': []})

        assert update.status == models.UpdateStatus.pending

    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.fetch_test_cases')
    @mock.patch('bodhi.server.tasks.updates.UpdatesHandler.work_on_bugs')
    def test_not_rawhide_update_signed_stays_pending(self, work_on_bugs, fetch_test_cases, sleep):
        """
        Assert that a non rawhide pending update that was edited does not get moved to testing
        if all the builds in the update are signed.
        """
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.status = models.UpdateStatus.pending
        update.release.composed_by_bodhi = True
        update.builds[0].signed = True

        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        h.run(api_version=1,
              data={
                  'action': 'edit',
                  'update': {'alias': update.alias, 'builds': [{'nvr': 'bodhi-2.0-1.fc17'}],
                             'user': {'name': 'bodhi'}, 'status': str(update.status),
                             'request': str(update.request)}, 'new_bugs': []})

        assert update.status == models.UpdateStatus.pending


class TestUpdatesHandlerInit:
    """This test class contains tests for the UpdatesHandler.__init__() method."""
    def test_handle_bugs_bodhi_email_falsey(self):
        """
        Assert that bug handling is disabled when bodhi_email is configured "falsey".
        """
        with mock.patch.dict(updates.config, {'bodhi_email': ''}):
            h = updates.UpdatesHandler()

        assert not h.handle_bugs

    def test_handle_bugs_bodhi_email_missing(self):
        """
        Assert that bug handling is disabled when bodhi_email is not configured.
        """
        replacement_config = copy.deepcopy(updates.config)
        del replacement_config['bodhi_email']

        with mock.patch.dict(updates.config, replacement_config, clear=True):
            h = updates.UpdatesHandler()

        assert not h.handle_bugs

    def test_typical_config(self):
        """
        Test the method with a typical config.
        """
        with mock.patch.dict(updates.config, {'bodhi_email': 'bowlofeggs@fpo.org'}):
            h = updates.UpdatesHandler()

        assert h.handle_bugs
        assert type(h.db_factory) == util.TransactionalSessionMaker


class TestUpdatesHandlerWorkOnBugs(base.BasePyTestCase):
    """This test class contains tests for the UpdatesHandler.work_on_bugs() method."""

    @mock.patch.dict(config.config, {'bodhi_email': None})
    @mock.patch('bodhi.server.tasks.updates.log.info')
    @mock.patch('bodhi.server.tasks.updates.log.warning')
    def test_bodhi_email_undefined(self, warning, info):
        """work_on_bugs() should log a warning and return if bodhi_email is not defined."""
        h = updates.UpdatesHandler()

        # The args don't matter because it should exit before trying to use any of them.
        h.work_on_bugs(None, None, None)

        # We should see warnings about bodhi_email being undefined.
        assert warning.mock_calls == [
            mock.call('No bodhi_email defined; not fetching bug details'),
            mock.call('Not configured to handle bugs')]

    def test_security_bug_sets_update_to_security(self):
        """Assert that associating a security bug with an Update changes the Update to security."""
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        update = self.db.query(models.Update).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()
        # The update should start out in a non-security state so we know that work_on_bugs() changed
        # it.
        assert update.type == models.UpdateType.bugfix
        bug = models.Bug.query.first()
        # Set this bug to security, so that the update gets switched to security.
        bug.security = True
        self.db.flush()
        bugs = self.db.query(models.Bug).all()

        h.work_on_bugs(h.db_factory, update, bugs)

        assert update.type == models.UpdateType.security

    @mock.patch('bodhi.server.tasks.updates.log.warning')
    def test_work_on_bugs_exception(self, warning):
        """
        Assert that work_on_bugs logs a warning when an exception is raised.
        """
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)

        update = self.db.query(models.Update).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()
        bugs = self.db.query(models.Bug).all()

        with mock.patch('bodhi.server.tasks.updates.bug_module.bugtracker.getbug',
                        side_effect=RuntimeError("oh no!")):
            h.work_on_bugs(h.db_factory, update, bugs)

        warning.assert_called_once_with('Error occurred during updating single bug', exc_info=True)


class TestUpdatesHandlerFetchTestCases(base.BasePyTestCase):
    """This test class contains tests for the UpdatesHandler.fetch_test_cases() method."""

    @mock.patch.dict(config.config, {'query_wiki_test_cases': True})
    @mock.patch('bodhi.server.models.MediaWiki')
    @mock.patch('bodhi.server.tasks.updates.log.warning')
    def test_fetch_test_cases_exception(self, warning, MediaWiki):
        """
        Assert that fetch_test_cases logs a warning when an exception is raised.
        """
        h = updates.UpdatesHandler()
        h.db_factory = base.TransactionalSessionMaker(self.Session)
        MediaWiki.return_value.call.side_effect = URLError("oh no!")

        update = self.db.query(models.Update).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()
        h.fetch_test_cases(h.db_factory, update)

        warning.assert_called_once_with('Error occurred during fetching testcases', exc_info=True)
