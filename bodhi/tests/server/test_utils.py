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
import subprocess
import unittest

import mock
import pkgdb2client

from bodhi.server import util
from bodhi.server.buildsys import setup_buildsystem, teardown_buildsystem
from bodhi.server.config import config


class TestUtils(object):

    def setUp(self):
        setup_buildsystem({'buildsystem': 'dev'})

    def tearDown(self):
        teardown_buildsystem()

    def test_config(self):
        assert config.get('sqlalchemy.url'), config
        assert config['sqlalchemy.url'], config

    def test_get_critpath_components_dummy(self):
        """ Ensure that critpath packages can be found using the hardcoded
        list.
        """
        pkgs = util.get_critpath_components()
        assert 'kernel' in pkgs, pkgs

    @mock.patch.object(pkgdb2client.PkgDB, 'get_critpath_packages')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pkgdb',
        'pkgdb_url': 'http://domain.local'
    })
    def test_get_critpath_components_pkgdb_success(self, mock_get_critpath):
        """ Ensure that critpath packages can be found using PkgDB.
        """
        # A subset of critpath packages
        critpath_pkgs = [
            'pth',
            'xorg-x11-server-utils',
            'giflib',
            'basesystem'
        ]
        mock_get_critpath.return_value = {
            'pkgs': {
                'f20': critpath_pkgs
            }
        }
        pkgs = util.get_critpath_components('f20')
        assert critpath_pkgs == pkgs, pkgs

    @mock.patch('bodhi.server.util.requests.get')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_get_critpath_components_pdc_error(self, mock_get):
        """ Ensure an error is thrown in Bodhi if there is an error in PDC
        getting the critpath packages.
        """
        mock_get.return_value.status_code = 500
        mock_get.return_value.json.return_value = \
            {'error': 'some error'}
        try:
            util.get_critpath_components('f25')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = unicode(error)
        # We are not testing the whole error message because there is no
        # guarantee of the ordering of the GET parameters.
        assert 'Bodhi failed to get a resource from PDC' in actual_error
        assert 'The status code was "500".' in actual_error

    @mock.patch('bodhi.server.util.log')
    @mock.patch.dict(util.config, {
        'critpath.type': 'dummy',
    })
    def test_get_critpath_components_not_pdc_not_rpm(self, mock_log):
        """ Ensure a warning is logged when the critpath system is not pdc
        and the type of components to search for is not rpm.
        """
        pkgs = util.get_critpath_components('f25', 'module')
        assert 'kernel' in pkgs, pkgs
        warning = ('The critpath.type of "module" does not support searching '
                   'for non-RPM components')
        mock_log.warning.assert_called_once_with(warning)

    @mock.patch('bodhi.server.util.requests.get')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_get_critpath_components_pdc_success(self, mock_get):
        """ Ensure that critpath packages can be found using PDC.
        """
        pdc_url = \
            'http://domain.local/rest_api/v1/component-branches/?page_size=1'
        pdc_next_url = '{0}&page=2'.format(pdc_url)
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.side_effect = [
            {
                'count': 2,
                'next': pdc_next_url,
                'previous': None,
                'results': [
                    {
                        'active': True,
                        'critical_path': True,
                        'global_component': 'gcc',
                        'id': 6,
                        'name': 'f26',
                        'slas': [],
                        'type': 'rpm'
                    }
                ]
            },
            {
                'count': 2,
                'next': None,
                'previous': pdc_url,
                'results': [
                    {
                        'active': True,
                        'critical_path': True,
                        'global_component': 'python',
                        'id': 7,
                        'name': 'f26',
                        'slas': [],
                        'type': 'rpm'
                    }
                ]
            }
        ]
        pkgs = util.get_critpath_components('f26')
        assert 'python' in pkgs and 'gcc' in pkgs, pkgs
        # At least make sure it called the next url to cycle through the pages.
        # We can't verify all the calls made because the URL GET parameters
        # in the URL may have different orders based on the system/Python
        # version.
        mock_get.assert_called_with(pdc_next_url, timeout=60)
        # Verify there were two GET requests made and two .json() calls
        assert mock_get.call_count == 2, mock_get.call_count
        assert mock_get.return_value.json.call_count == 2, \
            mock_get.return_value.json.call_count

    @mock.patch('bodhi.server.util.requests.get')
    def test_pagure_api_get(self, mock_get):
        """ Ensure that an API request to Pagure works as expected.
        """
        mock_get.return_value.status_code = 200
        expected_json = {
            "access_groups": {
                "admin": [],
                "commit": [],
                "ticket": []
            },
            "access_users": {
                "admin": [],
                "commit": [],
                "owner": [
                    "mprahl"
                ],
                "ticket": []
            },
            "close_status": [],
            "custom_keys": [],
            "date_created": "1494947106",
            "description": "Python",
            "fullname": "rpms/python",
            "id": 2,
            "milestones": {},
            "name": "python",
            "namespace": "rpms",
            "parent": None,
            "priorities": {},
            "tags": [],
            "user": {
                "fullname": "Matt Prahl",
                "name": "mprahl"
            }
        }
        mock_get.return_value.json.return_value = expected_json
        rv = util.pagure_api_get('http://domain.local/api/0/rpms/python')
        assert rv == expected_json, rv

    @mock.patch('bodhi.server.util.requests.get')
    def test_pagure_api_get_non_500_error(self, mock_get):
        """ Ensure that an API request to Pagure that raises an error that is
        not a 500 error returns the actual error message from the JSON.
        """
        mock_get.return_value.status_code = 404
        mock_get.return_value.json.return_value = {
            "error": "Project not found",
            "error_code": "ENOPROJECT"
        }
        try:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = unicode(error)

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"404". The error was "Project not found".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.requests.get')
    def test_pagure_api_get_500_error(self, mock_get):
        """ Ensure that an API request to Pagure that triggers a 500 error
        raises the expected error message.
        """
        mock_get.return_value.status_code = 500
        try:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = unicode(error)

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"500".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.requests.get')
    def test_pagure_api_get_non_500_error_no_json(self, mock_get):
        """ Ensure that an API request to Pagure that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        mock_get.return_value.status_code = 404
        mock_get.return_value.json.side_effect = ValueError('Not JSON')
        try:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = unicode(error)

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"404". The error was "".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.requests.get')
    def test_pdc_api_get(self, mock_get):
        """ Ensure that an API request to PDC works as expected.
        """
        mock_get.return_value.status_code = 200
        expected_json = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 1,
                    "sla": "security_fixes",
                    "branch": {
                        "id": 1,
                        "name": "2.7",
                        "global_component": "python",
                        "type": "rpm",
                        "active": True,
                        "critical_path": True
                    },
                    "eol": "2018-04-27"
                }
            ]
        }
        mock_get.return_value.json.return_value = expected_json
        rv = util.pdc_api_get(
            'http://domain.local/rest_api/v1/component-branch-slas/')
        assert rv == expected_json, rv

    @mock.patch('bodhi.server.util.requests.get')
    def test_pdc_api_get_500_error(self, mock_get):
        """ Ensure that an API request to PDC that triggers a 500 error
        raises the expected error message.
        """
        mock_get.return_value.status_code = 500
        try:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = unicode(error)

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/". The '
            'status code was "500".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.requests.get')
    def test_pdc_api_get_non_500_error(self, mock_get):
        """ Ensure that an API request to PDC that raises an error that is
        not a 500 error returns the returned JSON.
        """
        mock_get.return_value.status_code = 404
        mock_get.return_value.json.return_value = {
            "detail": "Not found."
        }
        try:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/3/')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = unicode(error)

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/3/". The '
            'status code was "404". The error was '
            '"{\'detail\': \'Not found.\'}".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.requests.get')
    def test_pdc_api_get_non_500_error_no_json(self, mock_get):
        """ Ensure that an API request to PDC that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        mock_get.return_value.status_code = 404
        mock_get.return_value.json.side_effect = ValueError('Not JSON')
        try:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/3/')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = unicode(error)

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/3/". The '
            'status code was "404". The error was "".')
        assert actual_error == expected_error, actual_error

    def test_get_nvr(self):
        """Assert the correct return value and type from get_nvr()."""
        result = util.get_nvr(u'ejabberd-16.12-3.fc26')

        assert result == ('ejabberd', '16.12', '3.fc26')
        for element in result:
            assert isinstance(element, unicode)

    def test_markup(self):
        """Ensure we escape HTML"""
        text = '<b>bold</b>'
        html = util.markup(None, text)
        assert html == (
            "<div class='markdown'>"
            '<p>&lt;b&gt;bold&lt;/b&gt;</p>'
            "</div>"
        ), html

    def test_rpm_header(self):
        h = util.get_rpm_header('')
        assert h['name'] == 'libseccomp', h

    def test_cmd_failure(self):
        try:
            util.cmd('false')
            assert False
        except Exception:
            pass

    def test_sorted_builds(self):
        new = 'bodhi-2.0-1.fc24'
        old = 'bodhi-1.5-4.fc24'
        b1, b2 = util.sorted_builds([new, old])
        assert b1 == new, b1
        assert b2 == old, b2


class TestCMDFunctions(unittest.TestCase):
    @mock.patch('bodhi.server.log.debug')
    @mock.patch('bodhi.server.log.error')
    @mock.patch('subprocess.Popen')
    def test_err_nonzero_return_code(self, mock_popen, mock_error, mock_debug):
        """
        Ensures proper behavior when there is err output and the exit code isn't 0.
        See https://github.com/fedora-infra/bodhi/issues/1412
        """
        mock_popen.return_value = mock.Mock()
        mock_popen_obj = mock_popen.return_value
        mock_popen_obj.communicate.return_value = ('output', 'error')
        mock_popen_obj.returncode = 1
        util.cmd('/bin/echo', '"home/imgs/catpix"')
        mock_popen.assert_called_once_with(['/bin/echo'], cwd='"home/imgs/catpix"',
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_error.assert_any_call('error')
        mock_debug.assert_called_once_with('output')

    @mock.patch('bodhi.server.log.debug')
    @mock.patch('bodhi.server.log.error')
    @mock.patch('subprocess.Popen')
    def test_no_err_zero_return_code(self, mock_popen, mock_error, mock_debug):
        """
        Ensures proper behavior when there is no err output and the exit code is 0.
        See https://github.com/fedora-infra/bodhi/issues/1412
        """
        mock_popen.return_value = mock.Mock()
        mock_popen_obj = mock_popen.return_value
        mock_popen_obj.communicate.return_value = ('output', None)
        mock_popen_obj.returncode = 0
        util.cmd('/bin/echo', '"home/imgs/catpix"')
        mock_popen.assert_called_once_with(['/bin/echo'], cwd='"home/imgs/catpix"',
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_error.assert_not_called()
        mock_debug.assert_called_once_with('output')

    @mock.patch('bodhi.server.log.debug')
    @mock.patch('bodhi.server.log.error')
    @mock.patch('subprocess.Popen')
    def test_err_zero_return_code(self, mock_popen, mock_error, mock_debug):
        """
        Ensures proper behavior when there is err output, but the exit code is 0.
        See https://github.com/fedora-infra/bodhi/issues/1412
        """
        mock_popen.return_value = mock.Mock()
        mock_popen_obj = mock_popen.return_value
        mock_popen_obj.communicate.return_value = ('output', 'error')
        mock_popen_obj.returncode = 0
        util.cmd('/bin/echo', '"home/imgs/catpix"')
        mock_popen.assert_called_once_with(['/bin/echo'], cwd='"home/imgs/catpix"',
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        mock_error.assert_not_called()
        mock_debug.assert_called_with('error')


class TestTransactionalSessionMaker(unittest.TestCase):
    """This class contains tests on the TransactionalSessionMaker class."""
    @mock.patch('bodhi.server.util.log.exception')
    @mock.patch('bodhi.server.util.Session')
    def test___call___fail_rollback_failure(self, Session, log_exception):
        """
        Ensure that __call__() correctly handles the failure case when rolling back itself fails.

        If the wrapped code raises an Exception *and* session.rollback() itself raises an Exception,
        __call__() should log the failure to roll back, and then close and remove the Session, and
        should raise the original Exception again.
        """
        tsm = util.TransactionalSessionMaker()
        exception = ValueError("u can't do that lol")
        # Now let's make it super bad by having rollback raise an Exception
        Session.return_value.rollback.side_effect = IOError("lol now u can't connect to the db")

        with self.assertRaises(ValueError) as exc_context:
            with tsm():
                raise exception

        log_exception.assert_called_once_with(
            'An Exception was raised while rolling back a transaction.')
        self.assertTrue(exc_context.exception is exception)
        self.assertEqual(Session.return_value.commit.call_count, 0)
        Session.return_value.rollback.assert_called_once_with()
        Session.return_value.close.assert_called_once_with()
        Session.remove.assert_called_once_with()

    @mock.patch('bodhi.server.util.log.exception')
    @mock.patch('bodhi.server.util.Session')
    def test___call___fail_rollback_success(self, Session, log_exception):
        """
        Ensure that __call__() correctly handles the failure case when rolling back is successful.

        If the wrapped code raises an Exception, __call__() should roll back the transaction, and
        close and remove the Session, and should raise the original Exception again.
        """
        tsm = util.TransactionalSessionMaker()
        exception = ValueError("u can't do that lol")

        with self.assertRaises(ValueError) as exc_context:
            with tsm():
                raise exception

        self.assertEqual(log_exception.call_count, 0)
        self.assertTrue(exc_context.exception is exception)
        self.assertEqual(Session.return_value.commit.call_count, 0)
        Session.return_value.rollback.assert_called_once_with()
        Session.return_value.close.assert_called_once_with()
        Session.remove.assert_called_once_with()

    @mock.patch('bodhi.server.util.log.exception')
    @mock.patch('bodhi.server.util.Session')
    def test___call___success(self, Session, log_exception):
        """
        Ensure that __call__() correctly handles the success case.

        __call__() should commit the transaction, and close and remove the Session upon a successful
        operation.
        """
        tsm = util.TransactionalSessionMaker()

        with tsm():
            pass

        self.assertEqual(log_exception.call_count, 0)
        self.assertEqual(Session.return_value.rollback.call_count, 0)
        Session.return_value.commit.assert_called_once_with()
        Session.return_value.close.assert_called_once_with()
        Session.remove.assert_called_once_with()
