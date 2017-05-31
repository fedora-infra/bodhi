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

    def test_get_critpath_pkgs(self):
        """Ensure the pkgdb's critpath API works"""
        pkgs = util.get_critpath_pkgs()
        assert 'kernel' in pkgs, pkgs

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
            '<p>--RAW HTML NOT ALLOWED--bold--RAW HTML NOT ALLOWED--</p>'
            "</div>"
        ), html

    def test_rpm_header(self):
        h = util.get_rpm_header('libseccomp')
        assert h['name'] == 'libseccomp', h

    def test_rpm_header_exception(self):
        try:
            util.get_rpm_header('raise-exception')
            assert False
        except Exception:
            pass

    def test_rpm_header_not_found(self):
        try:
            util.get_rpm_header("do-not-find-anything")
            assert False
        except ValueError:
            pass

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
