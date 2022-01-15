# Copyright © 2016-2019 Red Hat, Inc.
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
"""This test suite contains tests for the bodhi.server.buildsys module."""

from threading import Lock
from unittest import mock
import os

import koji
import pytest

from bodhi.server import buildsys


class TestTeardown:
    """This test class contains tests for the teardown_buildsystem() function."""

    def test_raises_not_configured(self):
        """
        buildsys.get_session requires buildsys.setup_buildsystem to be called first. Ensure
        that if not, we crash hard.
        """
        buildsys.teardown_buildsystem()
        pytest.raises(RuntimeError, buildsys.get_session)


class TestSetup:
    """This test class contains tests for the setup_buildsystem() function."""

    def test_raises_unknown_buildsys(self):
        """
        Ensure that we crash if we try to configure an invalid buildsys.
        """
        pytest.raises(ValueError, buildsys.setup_buildsystem, {'buildsystem': 'invalid'})


class TestGetKrbConf:
    """This class contains tests for the get_krb_conf() function."""
    def test_all_config_items_missing(self):
        """Assert behavior when all config items are missing."""
        config = {'some_meaningless_other_key': 'boring_value'}

        config = buildsys.get_krb_conf(config)

        assert config == {}

    def test_complete_config(self):
        """Assert behavior with a config that has all possible elements."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}

        config = buildsys.get_krb_conf(config)

        assert config == {'ccache': 'a_ccache', 'keytab': 'a_keytab', 'principal': 'a_principal'}

    def test_krb_ccache(self):
        """Assert behavior when only krb_ccache is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache'}

        config = buildsys.get_krb_conf(config)

        assert config == {'ccache': 'a_ccache'}

    def test_krb_ccache_uid(self):
        """Assert behavior for krb ccache uid replacement."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache_%{uid}'}

        config = buildsys.get_krb_conf(config)

        assert config == {'ccache': 'a_ccache_%d' % os.geteuid()}

    def test_krb_keytab(self):
        """Assert behavior when only krb_keytab is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_keytab': 'a_keytab'}

        config = buildsys.get_krb_conf(config)

        assert config == {'keytab': 'a_keytab'}

    def test_krb_principal(self):
        """Assert behavior when only krb_principal is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_principal': 'a_principal'}

        config = buildsys.get_krb_conf(config)

        assert config == {'principal': 'a_principal'}


class TestKojiLogin:
    """This class contains tests for the koji_login() function."""

    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.gssapi_login')
    @mock.patch('bodhi.server.buildsys.log.error')
    @mock.patch('time.sleep')
    def test_AuthError(self, sleep, error, gssapi_login):
        """backoff should take effect if an AuthError is raised."""
        gssapi_login.side_effect = [koji.AuthError, koji.AuthError, True]
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}
        default_koji_opts = {
            'krb_rdns': False,
            'max_retries': 30,
            'retry_interval': 10,
            'offline_retry': True,
            'offline_retry_interval': 10,
            'anon_retry': True,
        }

        client = buildsys.koji_login(config, authenticate=True)

        for key in default_koji_opts:
            assert default_koji_opts[key] == client.opts[key]
        assert type(client) == koji.ClientSession
        # Due to the use of backoff, we should have called gssapi_login three times.
        assert gssapi_login.mock_calls == (
            [mock.call(ccache='a_ccache', keytab='a_keytab', principal='a_principal')] * 3)
        # No error should have been logged
        assert error.call_count == 0
        # Make sure sleep was called twice, but we don't want to assert what values were used
        # because that's up to backoff and we don't want different versions of backoff to make
        # different choices and cause this test to fail.
        assert sleep.call_count == 2

    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.gssapi_login')
    @mock.patch('bodhi.server.buildsys.log.error')
    def test_authenticate_false(self, error, gssapi_login):
        """If authenticate is False, no attempt to call gssapi_login() shold be made."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}
        default_koji_opts = {
            'krb_rdns': False,
            'max_retries': 30,
            'retry_interval': 10,
            'offline_retry': True,
            'offline_retry_interval': 10,
            'anon_retry': True,
        }

        client = buildsys.koji_login(config, authenticate=False)

        for key in default_koji_opts:
            assert default_koji_opts[key] == client.opts[key]
        assert type(client) == koji.ClientSession
        # Since authenticate was False, the login should not have happened.
        assert gssapi_login.call_count == 0
        # No error should have been logged
        assert error.call_count == 0

    # gssapi_login returns a bool to indicate success or failure
    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.gssapi_login')
    @mock.patch('bodhi.server.buildsys.log.error')
    def test_login_failure(self, error, gssapi_login):
        """Assert correct behavior for a failed login event."""
        gssapi_login.return_value = False
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}

        client = buildsys.koji_login(config, authenticate=True)

        assert type(client) == koji.ClientSession
        gssapi_login.assert_called_once_with(ccache='a_ccache', keytab='a_keytab',
                                             principal='a_principal')
        error.assert_called_once_with('Koji gssapi_login failed')

    # gssapi_login returns a bool to indicate success or failure
    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.gssapi_login')
    @mock.patch('bodhi.server.buildsys.log.error')
    def test_login_success(self, error, gssapi_login):
        """Assert correct behavior for a successful login event."""
        gssapi_login.return_value = True
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}
        default_koji_opts = {
            'krb_rdns': False,
            'max_retries': 30,
            'retry_interval': 10,
            'offline_retry': True,
            'offline_retry_interval': 10,
            'anon_retry': True,
        }

        client = buildsys.koji_login(config, authenticate=True)

        for key in default_koji_opts:
            assert default_koji_opts[key] == client.opts[key]
        assert type(client) == koji.ClientSession
        gssapi_login.assert_called_once_with(ccache='a_ccache', keytab='a_keytab',
                                             principal='a_principal')
        # No error should have been logged
        assert error.call_count == 0


class TestGetSession:
    """Tests :func:`bodhi.server.buildsys.get_session` function"""

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    def test_uninitialized_buildsystem(self):
        """Assert calls to get_session raise RuntimeError when uninitialized"""
        pytest.raises(RuntimeError, buildsys.get_session)

    @mock.patch('bodhi.server.buildsys._buildsystem')
    @mock.patch('bodhi.server.buildsys._buildsystem_login_lock', wraps=Lock())
    def test_buildsys_lock(self, mock_lock, mock_buildsystem):
        """Assert the buildsystem lock is acquired and released in get_session"""
        buildsys.get_session()
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()
        mock_buildsystem.assert_called_once_with()


class TestSetupBuildsystem:
    """Tests :func:`bodhi.server.buildsys.setup_buildsystem` function"""

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.gssapi_login')
    def test_authenticate_false(self, gssapi_login):
        """If authenticate is set to False, the Koji client should should be unauthenticated."""
        config = {
            'krb_ccache': 'a_ccache', 'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal',
            'buildsystem': 'koji', 'koji_hub': 'https://example.com/koji'}
        assert buildsys._buildsystem is None

        buildsys.setup_buildsystem(config, authenticate=False)

        # Instantiating the buildsystem should not cause a gssapi_login to happen.
        buildsys._buildsystem()
        assert gssapi_login.call_count == 0

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.gssapi_login')
    def test_authenticate_true(self, gssapi_login):
        """If authenticate is set to True, the Koji client should should be authenticated."""
        config = {
            'krb_ccache': 'a_ccache', 'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal',
            'buildsystem': 'koji', 'koji_hub': 'https://example.com/koji'}
        assert buildsys._buildsystem is None

        buildsys.setup_buildsystem(config, authenticate=True)

        # Instantiating the buildsystem should cause a gssapi_login to happen.
        buildsys._buildsystem()
        gssapi_login.assert_called_once_with(ccache='a_ccache', keytab='a_keytab',
                                             principal='a_principal')

    @mock.patch('bodhi.server.buildsys._buildsystem', mock.Mock())
    def test_initialized_buildsystem(self):
        """Assert nothing happens when the buildsystem is already initialized"""
        old_buildsystem = buildsys._buildsystem
        buildsys.setup_buildsystem({})
        assert old_buildsystem is buildsys._buildsystem

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    @mock.patch('bodhi.server.buildsys.koji_login')
    def test_koji_buildsystem(self, mock_koji_login):
        """Assert the buildsystem initializes correctly for koji"""
        config = {'buildsystem': 'koji', 'some': 'key'}
        assert buildsys._buildsystem is None
        buildsys.setup_buildsystem(config)
        assert buildsys._buildsystem is not None
        buildsys._buildsystem()
        mock_koji_login.assert_called_once_with(authenticate=True, config=config)

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    def test_dev_buildsystem(self):
        """Assert the buildsystem initializes correctly for dev"""
        assert buildsys._buildsystem is None
        buildsys.setup_buildsystem({'buildsystem': 'dev'})
        assert buildsys._buildsystem is buildsys.DevBuildsys

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    def test_nonsense_buildsystem(self):
        """Assert the buildsystem setup crashes with nonsense values"""
        assert buildsys._buildsystem is None
        pytest.raises(ValueError, buildsys.setup_buildsystem,
                      {'buildsystem': 'Something unsupported'})


@mock.patch('bodhi.server.buildsys.log.debug')
class TestWaitForTasks:
    """Test the wait_for_tasks() function."""

    @mock.patch('bodhi.server.buildsys.time.sleep')
    def test_wait_on_unfinished_task(self, sleep, debug):
        """Assert that we wait on unfinished tasks for sleep seconds."""
        tasks = [1, 2, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, False, False, True, True]
        session.getTaskInfo.return_value = {'state': koji.TASK_STATES['CLOSED']}

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        assert ret == []
        assert debug.mock_calls == (
            [mock.call('Waiting for 3 tasks to complete: [1, 2, 3]'),
             mock.call('3 tasks completed successfully, 0 tasks failed.')])
        assert session.taskFinished.mock_calls == (
            [mock.call(1), mock.call(2), mock.call(2), mock.call(2), mock.call(3)])
        assert sleep.mock_calls == [mock.call(0.01), mock.call(0.01)]
        assert session.getTaskInfo.mock_calls == [mock.call(1), mock.call(2), mock.call(3)]

    def test_with_failed_task(self, debug):
        """Assert that we return a list of failed_tasks."""
        tasks = [1, 2, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, True, True]
        session.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['FAILED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        assert ret == [2]
        assert debug.mock_calls == (
            [mock.call('Waiting for 3 tasks to complete: [1, 2, 3]'),
             mock.call('2 tasks completed successfully, 1 tasks failed.')])
        assert session.taskFinished.mock_calls == [mock.call(1), mock.call(2), mock.call(3)]
        assert session.getTaskInfo.mock_calls == [mock.call(1), mock.call(2), mock.call(3)]

    def test_with_falsey_task(self, debug):
        """Assert that a Falsey entry in the list doesn't raise an Exception."""
        tasks = [1, False, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, True]
        session.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        assert ret == []
        assert debug.mock_calls == (
            [mock.call('Waiting for 3 tasks to complete: [1, False, 3]'),
             mock.call('Skipping task: False'),
             mock.call('3 tasks completed successfully, 0 tasks failed.')])
        assert session.taskFinished.mock_calls == [mock.call(1), mock.call(3)]
        assert session.getTaskInfo.mock_calls == [mock.call(1), mock.call(3)]

    def test_with_successful_tasks(self, debug):
        """A list of successful tasks should return []."""
        tasks = [1, 2, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, True, True]
        session.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        assert ret == []
        assert debug.mock_calls == (
            [mock.call('Waiting for 3 tasks to complete: [1, 2, 3]'),
             mock.call('3 tasks completed successfully, 0 tasks failed.')])
        assert session.taskFinished.mock_calls == [mock.call(1), mock.call(2), mock.call(3)]
        assert session.getTaskInfo.mock_calls == [mock.call(1), mock.call(2), mock.call(3)]

    @mock.patch('bodhi.server.buildsys.get_session')
    def test_without_session(self, get_session, debug):
        """Test the function without handing it a Koji session."""
        tasks = [1, 2, 3]
        get_session.return_value.taskFinished.side_effect = [True, True, True]
        get_session.return_value.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, sleep=0.01)

        assert ret == []
        assert debug.mock_calls == (
            [mock.call('Waiting for 3 tasks to complete: [1, 2, 3]'),
             mock.call('3 tasks completed successfully, 0 tasks failed.')])
        get_session.assert_called_once_with()
        assert get_session.return_value.taskFinished.mock_calls == (
            [mock.call(1), mock.call(2), mock.call(3)])
        assert get_session.return_value.getTaskInfo.mock_calls == (
            [mock.call(1), mock.call(2), mock.call(3)])
