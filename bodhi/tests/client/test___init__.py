# -*- coding: utf-8 -*-
# Copyright © 2016-2018 Red Hat, Inc. and others.
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
"""This module contains tests for bodhi.client."""
import datetime
import os
import platform
import unittest
import copy

from click import testing
import fedora.client
import mock
import munch
import six

from bodhi import client
from bodhi.client import bindings, AuthError
from bodhi.tests import client as client_test_data
from bodhi.tests.utils import compare_output

builtin_module_name = 'builtins' if six.PY3 else '__builtin__'

EXPECTED_DEFAULT_BASE_URL = os.environ.get('BODHI_URL', bindings.BASE_URL)


class TestComment(unittest.TestCase):
    """
    Test the comment() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMMENT_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.comment,
            ['nodejs-grunt-wrap-0.3.0-2.fc25', 'After installing this I found $100.', '--user',
             'bowlofeggs', '--password', 's3kr3t', '--url', 'http://localhost:6543', '--karma',
             '1'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_COMMENT_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'comments/', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'text': 'After installing this I found $100.',
                  'update': u'nodejs-grunt-wrap-0.3.0-2.fc25', 'email': None, 'karma': 1})
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')


class TestDownload(unittest.TestCase):
    """
    Test the download() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_url_flag(self, call, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output,
                         'Downloading packages from nodejs-grunt-wrap-0.3.0-2.fc25\n')
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'updates/', verb='GET',
            params={'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25'})
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')
        call.assert_called_once_with((
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_arch_flag(self, call, send_request):
        """
        Assert correct behavior with the --arch flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--arch', 'x86_64'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output,
                         'Downloading packages from nodejs-grunt-wrap-0.3.0-2.fc25\n')
        call.assert_called_once_with((
            'koji', 'download-build', '--arch=noarch', '--arch=x86_64',
            'nodejs-grunt-wrap-0.3.0-2.fc25'))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_arch_all_flag(self, call, send_request):
        """
        Assert correct behavior with --arch all flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--arch', 'all'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output,
                         'Downloading packages from nodejs-grunt-wrap-0.3.0-2.fc25\n')
        call.assert_called_once_with((
            'koji', 'download-build', 'nodejs-grunt-wrap-0.3.0-2.fc25'))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_empty_options(self, send_request):
        """
        Assert we return an error if either --cves --updateid or --builds are not
        used.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.download)

        self.assertEqual(result.output,
                         u'ERROR: must specify at least one of --cves, --updateid, --builds\n')
        send_request.assert_not_called()

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_no_builds_warning(self, call, send_request):
        """
        Test the download() no builds found warning.
        """
        runner = testing.CliRunner()
        no_builds_response = copy.copy(client_test_data.EXAMPLE_QUERY_MUNCH)
        no_builds_response.updates = []
        send_request.return_value = no_builds_response
        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-pants-0.3.0-2.fc25,nodejs-grunt-wrap-0.3.0-2.fc25'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, 'WARNING: No builds found!\n')
        call.assert_not_called()

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_some_builds_warning(self, call, send_request):
        """
        Test the download() some builds not found warning.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-pants-0.3.0-2.fc25,nodejs-grunt-wrap-0.3.0-2.fc25'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output,
                         'WARNING: Some builds not found!\nDownloading packages ' +
                         'from nodejs-grunt-wrap-0.3.0-2.fc25\n')
        call.assert_called_once_with((
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value="Failure")
    def test_download_failed_warning(self, call, send_request):
        """
        Test that we show a warning if a download fails.
        i.e. the subprocess call calling koji returns something.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output,
                         'Downloading packages from nodejs-grunt-wrap-0.3.0-2.fc25\n' +
                         'WARNING: download of nodejs-grunt-wrap-0.3.0-2.fc25 failed!\n')
        call.assert_called_once_with((
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'))


class TestListComposes(unittest.TestCase):
    """Test the list_composes() function."""
    @mock.patch.dict(client_test_data.EXAMPLE_COMPOSES_MUNCH,
                     {'composes': [client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0]]})
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSES_MUNCH, autospec=True)
    def test_single_compose(self, send_request):
        """Test without the -v flag."""
        runner = testing.CliRunner()

        result = runner.invoke(client.list_composes)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('*EPEL-7-stable  :   2 updates (requested)', result.output)
        self.assertNotIn(' EPEL-7-testing :   1 updates (requested)', result.output)
        bodhi_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bodhi_client, 'composes/', verb='GET')

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSES_MUNCH, autospec=True)
    def test_short(self, send_request):
        """Test without the -v flag."""
        runner = testing.CliRunner()

        result = runner.invoke(client.list_composes)

        self.assertEqual(result.exit_code, 0)
        self.assertIn('*EPEL-7-stable  :   2 updates (requested)', result.output)
        self.assertIn(' EPEL-7-testing :   1 updates (requested)', result.output)
        bodhi_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bodhi_client, 'composes/', verb='GET')

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSES_MUNCH, autospec=True)
    def test_verbose(self, send_request):
        """Test with the -v flag."""
        runner = testing.CliRunner()

        result = runner.invoke(client.list_composes, ['-v'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn('*EPEL-7-stable  :   2 updates (requested)', result.output)
        self.assertIn('Content Type: rpm', result.output)
        self.assertIn('Started: 2018-03-15 17:25:22', result.output)
        self.assertIn('Updated: 2018-03-15 17:25:22', result.output)
        self.assertIn('Updates:', result.output)
        self.assertIn('FEDORA-EPEL-2018-50566f0a39: uwsgi-2.0.16-1.el7', result.output)
        self.assertIn('FEDORA-EPEL-2018-328e2b8c27: qtpass-1.2.1-3.el7', result.output)
        self.assertIn('FEDORA-EPEL-2018-32f78e466c: libmodulemd-1.1.0-1.el7', result.output)
        self.assertIn(' EPEL-7-testing :   1 updates (requested)', result.output)
        bodhi_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bodhi_client, 'composes/', verb='GET')


class TestNew(unittest.TestCase):
    """
    Test the new() function.
    """

    @mock.patch.dict(client_test_data.EXAMPLE_UPDATE_MUNCH, {'severity': 'urgent'})
    @mock.patch.dict(os.environ, {'BODHI_URL': 'http://example.com/tests/'})
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_severity_flag(self, send_request):
        """Assert correct behavior with the --severity flag."""
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--severity', 'urgent'])

        self.assertEqual(result.exit_code, 0)
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('unspecified', 'urgent')
        self.assertTrue(compare_output(result.output, expected_output))
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': u'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': None, 'request': None, 'bugs': u'',
                    'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': 'urgent'
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        self.assertTrue(compare_output(result.output, expected_output))
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': u'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': None, 'request': None, 'bugs': u'',
                    'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.parse_file', autospec=True)
    def test_file_flag(self, parse_file):
        """
        Assert correct behavior with the --file flag.
        """
        runner = testing.CliRunner()

        runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--file', '/tmp/bodhiupdate.txt'])

        bindings_client = parse_file.mock_calls[0][1][0]

        parse_file.assert_called_once_with(bindings_client, u'/tmp/bodhiupdate.txt')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_bodhi_client_exception(self, send_request):
        """
        Assert that a BodhiClientException gets returned to the user via click echo
        """
        exception_message = "This is a BodhiClientException message"
        send_request.side_effect = bindings.BodhiClientException(exception_message)
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("This is a BodhiClientException message", result.output)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_exception(self, send_request):
        """
        Assert that any other Exception gets returned to the user as a traceback
        """
        exception_message = "This is an Exception message"
        send_request.side_effect = Exception(exception_message)
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Traceback (most recent call last):", result.output)
        self.assertIn("Exception: This is an Exception message", result.output)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_close_bugs_flag(self, send_request):
        """
        Assert correct behavior with the --close-bugs flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--bugs', '1234567', '--close-bugs', '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        self.assertTrue(compare_output(result.output, expected_output + '\n'))
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': True, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': u'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': None, 'request': None, 'bugs': u'1234567',
                    'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')


class TestPrintOverrideKojiHint(unittest.TestCase):
    """
    Test the _print_override_koji_hint() function.
    """
    @mock.patch('bodhi.client.click.echo')
    def test_with_release_id(self, echo):
        """Assert that the correct string is printed when the override Munch has a release_id."""
        override = munch.Munch({
            'submitter': munch.Munch({'name': 'bowlofeggs'}),
            'build': munch.Munch({'nvr': 'python-pyramid-1.5.6-3.fc25', 'release_id': 15}),
            'expiration_date': '2017-02-24'})
        c = bindings.BodhiClient()
        c.send_request = mock.MagicMock(
            return_value=munch.Munch({'releases': [munch.Munch({'dist_tag': 'f25'})]}))

        client._print_override_koji_hint(override, c)

        echo.assert_called_once_with(
            '\n\nUse the following to ensure the override is active:\n\n\t$ koji '
            'wait-repo f25-build --build=python-pyramid-1.5.6-3.fc25\n')
        c.send_request.assert_called_once_with('releases/', verb='GET',
                                               params={'ids': [15]})

    @mock.patch('bodhi.client.click.echo')
    def test_without_release_id(self, echo):
        """Assert that nothing is printed when the override Munch does not have a release_id."""
        override = munch.Munch({
            'submitter': {'name': 'bowlofeggs'}, 'build': {'nvr': 'python-pyramid-1.5.6-3.el7'},
            'expiration_date': '2017-02-24'})
        c = bindings.BodhiClient()
        c.send_request = mock.MagicMock(return_value='response')

        client._print_override_koji_hint(override, c)

        self.assertEqual(echo.call_count, 0)
        self.assertEqual(c.send_request.call_count, 0)


real_open = open


def fake_open_no_session_cache(*args, **kwargs):
    """Fake open so that it looks like we have no session cache."""
    if args[0] == fedora.client.openidbaseclient.b_SESSION_FILE:
        return mock.mock_open(read_data='{}')(*args, **kwargs)
    return real_open(*args, **kwargs)


class TestQuery(unittest.TestCase):
    """
    Test the query() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    def test_query_single_update(self, send_request):
        """
        Assert we display correctly when the query returns a single update.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_QUERY_OUTPUT + '\n')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'approved_since': None, 'status': None, 'locked': None,
                    'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25', 'releases': None,
                    'content_type': None,
                    'submitted_since': None, 'suggest': None, 'request': None, 'bugs': None,
                    'staging': False, 'modified_since': None, 'pushed': None,
                    'pushed_since': None, 'user': None, 'critpath': None, 'updateid': None,
                    'packages': None, 'type': None, 'cves': None, 'rows_per_page': None,
                    'page': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings._days_since',
                mock.MagicMock(return_value=17))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH_MULTI, autospec=True)
    def test_query_multiple_update(self, send_request):
        """
        Assert we display correctly when the query returns a single update.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXAMPLE_QUERY_OUTPUT_MULTI)
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'updates/', verb='GET',
            params={
                'approved_since': None, 'status': None, 'locked': None,
                'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25', 'releases': None,
                'content_type': None,
                'submitted_since': None, 'suggest': None, 'request': None, 'bugs': None,
                'staging': False, 'modified_since': None, 'pushed': None, 'pushed_since': None,
                'user': None, 'critpath': None, 'updateid': None, 'packages': None, 'type': None,
                'cves': None, 'rows_per_page': None, 'page': None})

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        expected_output = client_test_data.EXPECTED_QUERY_OUTPUT.replace('example.com/tests',
                                                                         'localhost:6543')
        self.assertEqual(result.output, expected_output + '\n')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'approved_since': None, 'status': None, 'locked': None,
                    'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25', 'releases': None,
                    'content_type': None,
                    'submitted_since': None, 'suggest': None, 'request': None, 'bugs': None,
                    'staging': False, 'modified_since': None, 'pushed': None,
                    'pushed_since': None, 'user': None, 'critpath': None, 'updateid': None,
                    'packages': None, 'type': None, 'cves': None, 'rows_per_page': None,
                    'page': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    def test_query_mine_flag_username_unset(self, mock_input, send_request):
        """Assert that we use init_username if --user is not given."""
        mock_input.return_value = 'dudemcpants'

        with mock.patch.dict('os.environ'):
            with mock.patch('{}.open'.format(builtin_module_name), create=True) as mock_open:
                mock_open.side_effect = fake_open_no_session_cache
                runner = testing.CliRunner()
                res = runner.invoke(client.query, ['--mine'])

        self.assertEqual(res.exit_code, 0)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'approved_since': None, 'status': None, 'locked': None,
                    'builds': None, 'releases': None,
                    'content_type': None,
                    'submitted_since': None, 'suggest': None, 'request': None, 'bugs': None,
                    'staging': False, 'modified_since': None, 'pushed': None, 'pushed_since': None,
                    'user': 'dudemcpants', 'critpath': None, 'updateid': None, 'packages': None,
                    'type': None, 'cves': None, 'rows_per_page': None, 'page': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        mock_open.assert_called_with(fedora.client.openidbaseclient.b_SESSION_FILE, 'rb')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    def test_rows_flag(self, send_request):
        """
        Assert correct behavior with the --rows flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query,
            ['--rows', 10])

        self.assertEqual(result.exit_code, 0)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'approved_since': None, 'status': None, 'locked': None,
                    'builds': None, 'releases': None,
                    'content_type': None,
                    'submitted_since': None, 'suggest': None, 'request': None, 'bugs': None,
                    'staging': False, 'modified_since': None, 'pushed': None, 'pushed_since': None,
                    'user': None, 'critpath': None, 'updateid': None, 'packages': None,
                    'type': None, 'cves': None, 'rows_per_page': 10, 'page': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    def test_page_flag(self, send_request):
        """
        Assert correct behavior with the --page flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query,
            ['--page', 5])

        self.assertEqual(result.exit_code, 0)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'approved_since': None, 'pushed': None, 'pushed_since': None,
                    'critpath': None, 'cves': None, 'rows_per_page': None, 'staging': False,
                    'submitted_since': None, 'suggest': None, 'updateid': None,
                    'type': None, 'status': None, 'releases': None, 'modified_since': None,
                    'user': None, 'content_type': None, 'packages': None, 'locked': None,
                    'builds': None, 'request': None, 'bugs': None, 'page': 5
                },
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)


class TestQueryBuildrootOverrides(unittest.TestCase):
    """
    This class tests the query_buildroot_overrides() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query_buildroot_overrides,
            ['--user', 'bowlofeggs', '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_QUERY_OVERRIDES_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'overrides/', verb='GET',
            params={'user': u'bowlofeggs'})
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    def test_queryoverrides_mine_flag_username_unset(self, mock_input, send_request):
        """Assert that we use init_username if --user is not given."""
        mock_input.return_value = 'dudemcpants'

        with mock.patch.dict('os.environ'):
            with mock.patch('{}.open'.format(builtin_module_name), create=True) as mock_open:
                mock_open.side_effect = fake_open_no_session_cache
                runner = testing.CliRunner()
                res = runner.invoke(client.query_buildroot_overrides, ['--mine'])

        self.assertEqual(res.exit_code, 0)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'overrides/', verb='GET', params={'user': 'dudemcpants'}
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        mock_open.assert_called_with(fedora.client.openidbaseclient.b_SESSION_FILE, 'rb')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_single_override(self, send_request):
        """Assert that querying a single override provides more detailed output."""
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_QUERY_SINGLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        send_request.side_effect = _send_request

        result = runner.invoke(client.query_buildroot_overrides,
                               ['--builds', 'bodhi-2.10.1-1.fc25'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            client_test_data.EXPECTED_OVERRIDES_OUTPUT + "1 overrides found (1 shown)\n")
        bindings_client = send_request.mock_calls[0][1][0]
        self.assertEqual(send_request.call_count, 2)
        self.assertEqual(
            send_request.mock_calls[0],
            mock.call(bindings_client, 'overrides/', verb='GET',
                      params={'builds': u'bodhi-2.10.1-1.fc25'}))
        self.assertEqual(
            send_request.mock_calls[1],
            mock.call(bindings_client, 'releases/', verb='GET',
                      params={'ids': [15]}))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH, autospec=True)
    def test_rows_flag(self, send_request):
        """
        Assert correct behavior with the --rows flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query_buildroot_overrides,
            ['--rows', 10])

        self.assertEqual(result.exit_code, 0)
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'overrides/', verb='GET',
            params={'rows_per_page': 10})

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH, autospec=True)
    def test_page_flag(self, send_request):
        """
        Assert correct behavior with the --page flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query_buildroot_overrides,
            ['--page', 5])

        self.assertEqual(result.exit_code, 0)
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'overrides/', verb='GET',
            params={'page': 5})


class TestRequest(unittest.TestCase):
    """
    This class tests the request() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(client.bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH)
    def test_successful_operation(self, send_request, __init__):
        """
        Assert that a successful updates request is handled properly.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.request, ['bodhi-2.2.4-1.el7', 'revoke', '--user',
                                                'some_user', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertTrue(compare_output(result.output, client_test_data.EXPECTED_UPDATE_OUTPUT))
        calls = [
            mock.call(
                'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
                data={
                    'csrf_token': 'a_csrf_token', 'request': u'revoke',
                    'update': u'bodhi-2.2.4-1.el7'
                }
            ),
            mock.call(
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        __init__.assert_called_once_with(base_url=EXPECTED_DEFAULT_BASE_URL, username='some_user',
                                         password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/request', status=404,
                    msg='update not found'))
    def test_update_not_found(self, send_request, __init__):
        """
        Assert that request() transforms a bodhi.client.bindings.UpdateNotFound into a
        click.BadParameter so that the user gets a nice error message.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.request, ['bodhi-2.2.4-99.el7', 'revoke', '--user',
                                                'some_user', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 2)
        self.assertTrue(compare_output(
            result.output,
            (u'Usage: request [OPTIONS] UPDATE STATE\n\nError: Invalid value for UPDATE: Update not'
             u' found: bodhi-2.2.4-99.el7\n')))
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-99.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': u'revoke',
                  'update': u'bodhi-2.2.4-99.el7'})
        __init__.assert_called_once_with(base_url=EXPECTED_DEFAULT_BASE_URL, username='some_user',
                                         password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.request,
            ['bodhi-2.2.4-99.el7', 'revoke', '--user', 'some_user', '--password', 's3kr3t', '--url',
             'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        self.assertTrue(compare_output(result.output, expected_output))
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/bodhi-2.2.4-99.el7/request', verb='POST', auth=True,
                data={
                    'csrf_token': 'a_csrf_token', 'request': u'revoke',
                    'update': u'bodhi-2.2.4-99.el7'
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')


class TestSaveBuilrootOverrides(unittest.TestCase):
    """
    Test the save_buildroot_overrides() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        send_request.side_effect = _send_request

        result = runner.invoke(
            client.save_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25', '--url',
             'http://localhost:6543/'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_OVERRIDES_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = send_request.mock_calls[0][2]['data']['expiration_date']
        self.assertTrue((datetime.datetime.utcnow() - expire_time) < datetime.timedelta(seconds=5))
        # There should be two calls to send_request(). The first to save the override, and the
        # second to find out the release tags so the koji wait-repo hint can be printed.
        self.assertEqual(send_request.call_count, 2)
        self.assertEqual(
            send_request.mock_calls[0],
            mock.call(
                bindings_client, 'overrides/', verb='POST', auth=True,
                data={
                    'expiration_date': expire_time,
                    'notes': u'No explanation given...', 'nvr': u'js-tag-it-2.0-1.fc25',
                    'csrf_token': 'a_csrf_token'}))
        self.assertEqual(
            send_request.mock_calls[1],
            mock.call(
                bindings_client, 'releases/', verb='GET',
                params={'ids': [15]}))
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_existing_override_error_message(self, send_request):
        """
        Assert that the error message is provided if we try to save an existing override
        """
        exception_message = "Buildroot override for js-tag-it-2.0-1.fc25 already exists"
        send_request.side_effect = bindings.BodhiClientException(exception_message)
        runner = testing.CliRunner()

        result = runner.invoke(
            client.save_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("The `overrides save` command is used for creating a new override",
                      result.output)
        self.assertIn("Use `overrides edit` to edit an existing override",
                      result.output)


class TestWarnIfUrlAndStagingSet(unittest.TestCase):
    """
    This class tests the _warn_if_url_and_staging_set() function.
    """
    @mock.patch('bodhi.client.click.echo')
    def test_staging_false(self, echo):
        """
        Nothing should be printed when staging is False.
        """
        ctx = mock.MagicMock()
        ctx.params = {'staging': False}

        result = client._warn_if_url_and_staging_set(ctx, mock.MagicMock(),
                                                     'http://localhost:6543')

        self.assertEqual(result, 'http://localhost:6543')
        self.assertEqual(echo.call_count, 0)

    @mock.patch('bodhi.client.click.echo')
    def test_staging_missing(self, echo):
        """
        Nothing should be printed when staging is not present in the context.
        """
        ctx = mock.MagicMock()
        ctx.params = {}

        result = client._warn_if_url_and_staging_set(ctx, mock.MagicMock(),
                                                     'http://localhost:6543')

        self.assertEqual(result, 'http://localhost:6543')
        self.assertEqual(echo.call_count, 0)

    @mock.patch('bodhi.client.click.echo')
    def test_staging_true(self, echo):
        """
        A warning should be printed to stderr when staging is True.
        """
        ctx = mock.MagicMock()
        ctx.params = {'staging': True}

        result = client._warn_if_url_and_staging_set(ctx, mock.MagicMock(),
                                                     'http://localhost:6543')

        self.assertEqual(result, 'http://localhost:6543')
        echo.assert_called_once_with(
            '\nWarning: url and staging flags are both set. url will be ignored.\n', err=True)


class TestEdit(unittest.TestCase):
    """
    This class tests the edit() function.
    """

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_severity_flag(self, send_request, query):
        """Assert that the --severity flag is handled properly."""
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-cc8582d738', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--severity', 'low'])

        self.assertEqual(result.exit_code, 0)
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid=u'FEDORA-2017-cc8582d738')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                    'autokarma': False, 'edited': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                    'suggest': None, 'notes': None, 'notes_file': None, 'requirements': None,
                    'request': None, 'bugs': u'', 'unstable_karma': None, 'type': 'bugfix',
                    'severity': 'low'
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_url_flag(self, send_request, query):
        """
        Assert that a successful updates edit request is handled properly.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-cc8582d738', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'this is an edited note',
                          '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid=u'FEDORA-2017-cc8582d738')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                    'autokarma': False, 'edited': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                    'suggest': None, 'notes': u'this is an edited note', 'notes_file': None,
                    'requirements': None, 'request': None, 'bugs': u'', 'unstable_karma': None,
                    'type': 'bugfix', 'severity': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_notes_file(self, send_request, query):
        """
        Assert that a valid notes-file is properly handled in a successful updates
        edit request.
        """
        runner = testing.CliRunner()
        with runner.isolated_filesystem():
            with open('notefile.txt', 'w') as f:
                f.write('This is a --notes-file note!')

            result = runner.invoke(
                client.edit, ['FEDORA-2017-cc8582d738', '--user', 'bowlofeggs',
                              '--password', 's3kr3t', '--notes-file', 'notefile.txt',
                              '--url', 'http://localhost:6543'])

            self.assertEqual(result.exit_code, 0)
            bindings_client = query.mock_calls[0][1][0]
            query.assert_called_with(
                bindings_client, updateid=u'FEDORA-2017-cc8582d738')
            bindings_client = send_request.mock_calls[0][1][0]
            calls = [
                mock.call(
                    bindings_client, 'updates/', auth=True, verb='POST',
                    data={
                        'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                        'staging': False, 'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                        'autokarma': False, 'edited': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                        'suggest': None, 'notes': 'This is a --notes-file note!',
                        'notes_file': 'notefile.txt', 'request': None, 'bugs': u'',
                        'requirements': None, 'unstable_karma': None, 'type': 'bugfix',
                        'severity': None
                    }
                ),
                mock.call(
                    bindings_client,
                    u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                    verb='GET'
                )
            ]
            self.assertEqual(send_request.mock_calls, calls)
            self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    def test_notes_and_notes_file(self):
        """
        Assert providing both --notes-file and --notes parameters to an otherwise successful
        updates edit request results in an error.
        """
        runner = testing.CliRunner()
        with runner.isolated_filesystem():
            with open('notefile.txt', 'w') as f:
                f.write('This is a --notes-file note!')

            result = runner.invoke(
                client.edit, ['FEDORA-2017-cc8582d738', '--user', 'bowlofeggs',
                              '--password', 's3kr3t', '--notes', 'this is a notey note',
                              '--notes-file', 'notefile.txt', '--url', 'http://localhost:6543'])

            self.assertEqual(result.exit_code, 1)
            self.assertEqual(result.output, u'ERROR: Cannot specify --notes and --notes-file\n')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_update_title(self, send_request):
        """
        Assert that we can successfully edit an update using the update title.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['drupal7-i18n-1.17-1.fc26', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'this is an edited note',
                          '--url', 'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': u'drupal7-i18n-1.17-1.fc26', 'autokarma': False,
                    'edited': u'drupal7-i18n-1.17-1.fc26', 'suggest': None, 'requirements': None,
                    'notes': u'this is an edited note', 'notes_file': None,
                    'request': None, 'bugs': u'', 'unstable_karma': None, 'type': 'bugfix',
                    'severity': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)

    def test_wrong_update_title_argument(self):
        """
         Assert that an error is given if the edit update argument given is not an update id
         nor an update title.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['drupal7-i18n-1.17-1', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'this is an edited note',
                          '--url', 'http://localhost:6543'])
        self.assertEqual(result.exit_code, 2)
        expected = u'Usage: edit [OPTIONS] UPDATE\n\n' \
                   u'Error: Invalid value for "update": ' \
                   u'Please provide an Update ID or an Update Title\n'

        self.assertEqual(result.output, expected)

    def test_wrong_update_id_argument(self):
        """
         Assert that an error is given if the edit update argument given is not an update id
         nor an update title.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-20-cc8582d738', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'this is an edited note',
                          '--url', 'http://localhost:6543'])
        self.assertEqual(result.exit_code, 2)
        expected = u'Usage: edit [OPTIONS] UPDATE\n\n' \
                   u'Error: Invalid value for "update": ' \
                   u'Please provide an Update ID or an Update Title\n'

        self.assertEqual(result.output, expected)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_required_tasks(self, send_request, query):
        """
        Assert that valid required Taskotron Tasks are properly handled in a successful updates
        edit request.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-cc8582d738', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'testing required tasks',
                          '--requirements', 'dist.depcheck dist.rpmdeplint', '--url',
                          'http://localhost:6543'])

        self.assertEqual(result.exit_code, 0)
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid=u'FEDORA-2017-cc8582d738')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                    'autokarma': False, 'edited': u'nodejs-grunt-wrap-0.3.0-2.fc25',
                    'suggest': None, 'notes': u'testing required tasks', 'notes_file': None,
                    'requirements': u'dist.depcheck dist.rpmdeplint', 'request': None,
                    'bugs': u'', 'unstable_karma': None, 'type': 'bugfix', 'severity': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        self.assertEqual(send_request.mock_calls, calls)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_bodhi_client_exception(self, send_request):
        """
        Assert that a BodhiClientException gets returned to the user via click echo
        """
        exception_message = "This is a BodhiClientException message"
        send_request.side_effect = bindings.BodhiClientException(exception_message)
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-cc8582d738', '--user', 'bowlofeggs',
                          '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("This is a BodhiClientException message", result.output)


class TestEditBuilrootOverrides(unittest.TestCase):
    """
    Test the edit_buildroot_overrides() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_EXPIRED_OVERRIDE_MUNCH, autospec=True)
    def test_expired_override(self, send_request):
        """
        Assert that a successful overrides edit request expires the request
        when --expired flag is set.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25', '--url',
             'http://localhost:6543/', '--notes', 'This is an expired override', '--expire'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_EXPIRED_OVERRIDES_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = send_request.mock_calls[0][2]['data']['expiration_date']
        self.assertTrue((datetime.datetime.utcnow() - expire_time) < datetime.timedelta(seconds=5))
        send_request.assert_called_once_with(
            bindings_client, 'overrides/', verb='POST', auth=True,
            data={
                'expiration_date': expire_time, 'notes': u'This is an expired override',
                'nvr': u'js-tag-it-2.0-1.fc25', 'edited': u'js-tag-it-2.0-1.fc25',
                'csrf_token': 'a_csrf_token', 'expired': True})
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')


class TestCreate(unittest.TestCase):
    """
    Test the create() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.create_release,
            ['--name', 'F27', '--url', 'http://localhost:6543', '--username', 'bowlofeggs',
             '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_RELEASE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': None, 'csrf_token': 'a_csrf_token', 'staging': False, 'name': u'F27',
                  'testing_tag': None, 'pending_stable_tag': None, 'long_name': None, 'state': None,
                  'version': None, 'override_tag': None, 'branch': None, 'id_prefix': None,
                  'pending_testing_tag': None, 'stable_tag': None, 'candidate_tag': None})
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value={"errors": [{"description": "an error was encountered... :("}]},
                autospec=True)
    def test_create_with_errors(self, send_request):
        """
        Assert errors are printed if returned back in the request
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.create_release,
            ['--name', 'F27', '--url', 'http://localhost:6543', '--username', 'bowlofeggs',
             '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, "ERROR: an error was encountered... :(\n")


class TestEditRelease(unittest.TestCase):
    """
    Test the edit_release() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_release,
            ['--name', 'F27', '--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_RELEASE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        self.assertEqual(send_request.call_count, 2)
        self.assertEqual(send_request.mock_calls[0],
                         mock.call(bindings_client, 'releases/F27', verb='GET', auth=True))
        self.assertEqual(
            send_request.mock_calls[1],
            mock.call(
                bindings_client, 'releases/', verb='POST', auth=True,
                data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'staging': False,
                      'name': 'F27', 'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                      'pending_stable_tag': 'f27-updates-pending',
                      'pending_signing_tag': 'f27-signing-pending',
                      'long_name': 'Fedora 27, the Greatest Fedora!', 'state': 'pending',
                      'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                      'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                      'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate'}))
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_new_name_flag(self, send_request):
        """
        Assert correct behavior with the --new-name flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_release,
            ['--name', 'F27', '--new-name', 'fedora27', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, client_test_data.EXPECTED_RELEASE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        self.assertEqual(send_request.call_count, 2)
        self.assertEqual(send_request.mock_calls[0],
                         mock.call(bindings_client, 'releases/F27', verb='GET', auth=True))
        self.assertEqual(
            send_request.mock_calls[1],
            mock.call(
                bindings_client, 'releases/', verb='POST', auth=True,
                data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'staging': False,
                      'name': 'fedora27', 'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                      'pending_stable_tag': 'f27-updates-pending',
                      'pending_signing_tag': 'f27-signing-pending',
                      'long_name': 'Fedora 27', 'state': 'pending',
                      'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                      'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                      'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate'}))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_edit_no_name_provided(self, send_request):
        """
        Assert we print an error and no request is sent if a --name is not provided.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_release,
            ['--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.output, ("ERROR: Please specify the name of the release to edit\n"))
        send_request.assert_not_called()

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value={"errors": [{"description": "an error was encountered... :("}]},
                autospec=True)
    def test_edit_with_errors(self, send_request):
        """
        Assert errors are printed if returned back in the request
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_release,
            ['--name', 'F27', '--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, ("ERROR: an error was encountered... :(\n"))


class TestInfo(unittest.TestCase):
    """
    Test the info() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.info_release, ['--url', 'http://localhost:6543', 'F27'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output,
                         client_test_data.EXPECTED_RELEASE_OUTPUT.replace('Saved r', 'R'))
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bindings_client, 'releases/F27', verb='GET',
                                             auth=False)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value={"errors": [{"description": "an error was encountered... :("}]},
                autospec=True)
    def test_info_with_errors(self, send_request):
        """
        Assert errors are printed if returned back in the request
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.info_release, ['--url', 'http://localhost:6543', 'F27'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, ("ERROR: an error was encountered... :(\n"))


class TestHandleErrors(unittest.TestCase):
    """
    Test the handle_errors decorator
    """

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_bodhi_client_exception(self, send_request):
        """
        Assert that BodhiClientExceptions are presented as expected
        """
        send_request.side_effect = bindings.BodhiClientException("Pants Exception")
        runner = testing.CliRunner()

        result = runner.invoke(
            client.save_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25'])

        self.assertEqual(result.exit_code, 2)
        self.assertEqual("Pants Exception\n", result.output)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_other_client_exception(self, send_request):
        """
        Assert that AuthErrors are presented as expected
        """
        send_request.side_effect = AuthError("Authentication failed")
        runner = testing.CliRunner()

        result = runner.invoke(
            client.save_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual("Authentication failed: Check your FAS username & password\n",
                         result.output)


class TestPrintResp(unittest.TestCase):
    """
    Test the print_resp() method.
    """

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.SINGLE_UPDATE_MUNCH, autospec=True)
    def test_single_update(self, send_request):
        """
        Test the single update response returns the update.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query,
            ['--url', 'http://localhost:6543'])

        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        self.assertTrue(compare_output(result.output, expected_output))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.UNMATCHED_RESP, autospec=True)
    def test_unhandled_response(self, send_request):
        """
        Test that if a response is not identified by print_resp, then we just print the response
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.query,
            [])

        self.assertEqual(result.output, u"{'pants': 'pants'}\n")

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_OVERRIDE_MUNCH_CAVEATS, autospec=True)
    def test_caveats_output(self, send_request):
        """
        Assert we correctly output caveats.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.save_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25'])

        self.assertIn("\nCaveats:\nthis is a caveat\n", result.output)
