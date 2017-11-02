# -*- coding: utf-8 -*-
# Copyright © 2016-2017 Red Hat, Inc.
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
import unittest

import koji
import mock

from bodhi.server import buildsys


class TestBuildsystem(unittest.TestCase):
    """This test class contains tests for the Buildsystem class."""
    def test_raises_not_implemented(self):
        """
        TheBuildsystem class is meant to be a superclass, so each of its methods raise
        NotImplementedError. Ensure that this is raised.
        """
        bs = buildsys.Buildsystem()

        for method in (
                bs.getBuild, bs.getLatestBuilds, bs.moveBuild, bs.ssl_login, bs.listBuildRPMs,
                bs.listTags, bs.listTagged, bs.taskFinished, bs.tagBuild, bs.untagBuild,
                bs.multiCall, bs.getTag):
            self.assertRaises(NotImplementedError, method)

    def test_raises_not_configured(self):
        """
        buildsys.get_session requires buildsys.setup_buildsystem to be called first. Ensure
        that if not, we crash hard.
        """
        buildsys.teardown_buildsystem()
        self.assertRaises(RuntimeError, buildsys.get_session)

    def test_raises_unknown_buildsys(self):
        """
        Ensure that we crash if we try to configure an invalid buildsys.
        """
        self.assertRaises(ValueError, buildsys.setup_buildsystem, {'buildsystem': 'invalid'})


class TestGetKrbConf(unittest.TestCase):
    """This class contains tests for the get_krb_conf() function."""
    def test_all_config_items_missing(self):
        """Assert behavior when all config items are missing."""
        config = {'some_meaningless_other_key': 'boring_value'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {})

    def test_complete_config(self):
        """Assert behavior with a config that has all possible elements."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config,
                         {'ccache': 'a_ccache', 'keytab': 'a_keytab', 'principal': 'a_principal'})

    def test_krb_ccache(self):
        """Assert behavior when only krb_ccache is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {'ccache': 'a_ccache'})

    def test_krb_keytab(self):
        """Assert behavior when only krb_keytab is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_keytab': 'a_keytab'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {'keytab': 'a_keytab'})

    def test_krb_principal(self):
        """Assert behavior when only krb_prinicpal is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_principal': 'a_principal'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {'principal': 'a_principal'})


class TestKojiLogin(unittest.TestCase):
    """This class contains tests for the koji_login() function."""
    # krb_login returns a bool to indicate success or failure
    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.krb_login',
                mock.MagicMock(return_value=False))
    @mock.patch('bodhi.server.buildsys.log.error')
    def test_login_failure(self, error):
        """Assert correct behavior for a failed login event."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}

        client = buildsys.koji_login(config)

        self.assertEqual(type(client), koji.ClientSession)
        error.assert_called_once_with('Koji krb_login failed')

    # krb_login returns a bool to indicate success or failure
    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.krb_login',
                mock.MagicMock(return_value=True))
    @mock.patch('bodhi.server.buildsys.log.error')
    def test_login_success(self, error):
        """Assert correct behavior for a successful login event."""
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

        client = buildsys.koji_login(config)
        for key in default_koji_opts:
            self.assertEqual(default_koji_opts[key], client.opts[key])

        self.assertEqual(type(client), koji.ClientSession)
        # No error should have been logged
        self.assertEqual(error.call_count, 0)


class TestGetSession(unittest.TestCase):
    """Tests :func:`bodhi.server.buildsys.get_session` function"""

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    def test_uninitialized_buildsystem(self):
        """Assert calls to get_session raise RuntimeError when uninitialized"""
        self.assertRaises(RuntimeError, buildsys.get_session)

    @mock.patch('bodhi.server.buildsys._buildsystem')
    @mock.patch('bodhi.server.buildsys._buildsystem_login_lock', wraps=Lock())
    def test_buildsys_lock(self, mock_lock, mock_buildsystem):
        """Assert the buildsystem lock is aquired and released in get_session"""
        buildsys.get_session()
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()
        mock_buildsystem.assert_called_once_with()


class TestSetupBuildsystem(unittest.TestCase):
    """Tests :func:`bodhi.server.buildsys.setup_buildsystem` function"""

    @mock.patch('bodhi.server.buildsys._buildsystem', mock.Mock())
    def test_initialized_buildsystem(self):
        """Assert nothing happens when the buildsystem is already initialized"""
        old_buildsystem = buildsys._buildsystem
        buildsys.setup_buildsystem({})
        self.assertTrue(old_buildsystem is buildsys._buildsystem)

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    @mock.patch('bodhi.server.buildsys.koji_login')
    def test_koji_buildsystem(self, mock_koji_login):
        """Assert the buildsystem initializes correctly for koji"""
        config = {'buildsystem': 'koji', 'some': 'key'}
        self.assertTrue(buildsys._buildsystem is None)
        buildsys.setup_buildsystem(config)
        self.assertFalse(buildsys._buildsystem is None)
        buildsys._buildsystem()
        mock_koji_login.assert_called_once_with(config=config)

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    def test_dev_buildsystem(self):
        """Assert the buildsystem initializes correctly for dev"""
        self.assertTrue(buildsys._buildsystem is None)
        buildsys.setup_buildsystem({'buildsystem': 'dev'})
        self.assertTrue(buildsys._buildsystem is buildsys.DevBuildsys)

    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    def test_nonsense_buildsystem(self):
        """Assert the buildsystem setup crashes with nonsense values"""
        self.assertTrue(buildsys._buildsystem is None)
        self.assertRaises(ValueError, buildsys.setup_buildsystem,
                          {'buildsystem': 'Something unsupported'})


class TestWaitForTasks(unittest.TestCase):
    """Test the wait_for_tasks() function."""

    @mock.patch('bodhi.server.buildsys.time.sleep')
    def test_wait_on_unfinished_task(self, sleep):
        """Assert that we wait on unfinished tasks for sleep seconds."""
        tasks = [1, 2, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, False, False, True, True]
        session.getTaskInfo.return_value = {'state': koji.TASK_STATES['CLOSED']}

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        self.assertEqual(ret, [])
        self.assertEqual(session.taskFinished.mock_calls,
                         [mock.call(1), mock.call(2), mock.call(2), mock.call(2), mock.call(3)])
        self.assertEqual(sleep.mock_calls, [mock.call(0.01), mock.call(0.01)])
        self.assertEqual(session.getTaskInfo.mock_calls, [mock.call(1), mock.call(2), mock.call(3)])

    def test_with_failed_task(self):
        """Assert that we return a list of failed_tasks."""
        tasks = [1, 2, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, True, True]
        session.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['FAILED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        self.assertEqual(ret, [2])
        self.assertEqual(session.taskFinished.mock_calls,
                         [mock.call(1), mock.call(2), mock.call(3)])
        self.assertEqual(session.getTaskInfo.mock_calls, [mock.call(1), mock.call(2), mock.call(3)])

    @mock.patch('bodhi.server.buildsys.log.debug')
    def test_with_falsey_task(self, debug):
        """Assert that a Falsey entry in the list doesn't raise an Exception."""
        tasks = [1, False, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, True]
        session.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        self.assertEqual(ret, [])
        self.assertEqual(
            debug.mock_calls,
            [mock.call('Waiting for 3 tasks to complete: [1, False, 3]'),
             mock.call('Skipping task: False'),
             mock.call('Tasks completed successfully!')])
        self.assertEqual(session.taskFinished.mock_calls,
                         [mock.call(1), mock.call(3)])
        self.assertEqual(session.getTaskInfo.mock_calls, [mock.call(1), mock.call(3)])

    def test_with_successful_tasks(self):
        """A list of successful tasks should return []."""
        tasks = [1, 2, 3]
        session = mock.MagicMock()
        session.taskFinished.side_effect = [True, True, True]
        session.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, session, sleep=0.01)

        self.assertEqual(ret, [])
        self.assertEqual(session.taskFinished.mock_calls,
                         [mock.call(1), mock.call(2), mock.call(3)])
        self.assertEqual(session.getTaskInfo.mock_calls, [mock.call(1), mock.call(2), mock.call(3)])

    @mock.patch('bodhi.server.buildsys.get_session')
    def test_without_session(self, get_session):
        """Test the function without handing it a Koji session."""
        tasks = [1, 2, 3]
        get_session.return_value.taskFinished.side_effect = [True, True, True]
        get_session.return_value.getTaskInfo.side_effect = [
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']},
            {'state': koji.TASK_STATES['CLOSED']}]

        ret = buildsys.wait_for_tasks(tasks, sleep=0.01)

        self.assertEqual(ret, [])
        get_session.assert_called_once_with()
        self.assertEqual(get_session.return_value.taskFinished.mock_calls,
                         [mock.call(1), mock.call(2), mock.call(3)])
        self.assertEqual(get_session.return_value.getTaskInfo.mock_calls,
                         [mock.call(1), mock.call(2), mock.call(3)])
