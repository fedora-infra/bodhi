# Copyright © 2016-2019 Red Hat, Inc. and others.
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
from unittest import mock
import datetime
import os
import platform
import tempfile
import copy

from click import testing
import click
import fedora.client
import munch

from bodhi import client
from bodhi.client import bindings, AuthError
from bodhi.tests import client as client_test_data
from bodhi.tests.utils import compare_output


EXPECTED_DEFAULT_BASE_URL = os.environ.get('BODHI_URL', bindings.BASE_URL)


UPDATE_FILE = '''[fedora-workstation-backgrounds-1.1-1.fc26]
# bugfix, security, enhancement, newpackage (required)
type=bugfix

# testing, stable
request=testing

# Bug numbers: 1234,9876
bugs=123456,43212

# Here is where you give an explanation of your update.
notes=Initial Release

# Update name
display_name=fake update name

# Enable request automation based on the stable/unstable karma thresholds
autokarma=True
stable_karma=3
unstable_karma=-3

# Automatically close bugs when this marked as stable
close_bugs=True

# Suggest that users restart after update
suggest_reboot=False
'''


class TestComment:
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

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_COMMENT_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'comments/', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'text': 'After installing this I found $100.',
                  'update': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'karma': 1})
        assert bindings_client.base_url == 'http://localhost:6543/'


class TestDownload:
    """
    Test the download() function.
    """

    EXAMPLE_QUERY_MUNCH_MULTI_BUILDS = copy.deepcopy(client_test_data.EXAMPLE_QUERY_MUNCH)
    EXAMPLE_QUERY_MUNCH_MULTI_BUILDS.updates[0]['builds'].append({
        'epoch': 0,
        'nvr': 'nodejs-pants-0.3.0-2.fc25',
        'signed': True
    })

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

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'updates/', verb='GET',
            params={'builds': 'nodejs-grunt-wrap-0.3.0-2.fc25'})
        assert bindings_client.base_url == 'http://localhost:6543/'
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

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

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch=x86_64',
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

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

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_called_once_with([
            'koji', 'download-build', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_debuginfo_flag(self, call, send_request):
        """
        Assert correct behavior with --debuginfo flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--arch', 'all', '--debuginfo'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_called_once_with([
            'koji', 'download-build', '--debuginfo', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=EXAMPLE_QUERY_MUNCH_MULTI_BUILDS, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_multiple_builds(self, call, send_request):
        """
        Assert correct behavior with multiple builds.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--builds', 'nodejs-pants-0.3.0-2.fc25,nodejs-grunt-wrap-0.3.0-2.fc25',
             '--arch', 'all'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_any_call([
            'koji', 'download-build', 'nodejs-pants-0.3.0-2.fc25'])
        call.assert_any_call([
            'koji', 'download-build', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_empty_options(self, send_request):
        """Assert we return an error if either --updateid or --builds are not used."""
        runner = testing.CliRunner()

        result = runner.invoke(client.download)

        assert result.output == 'ERROR: must specify at least one of --updateid or --builds\n'
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

        assert result.exit_code == 0
        assert result.output == 'WARNING: No builds found!\n'
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

        assert result.exit_code == 0
        assert result.output == ('WARNING: Some builds not found!\nDownloading packages '
                                 'from FEDORA-2017-c95b33872d\n')
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

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

        assert result.exit_code == 0
        assert result.output == ('Downloading packages from FEDORA-2017-c95b33872d\n'
                                 'WARNING: download of nodejs-grunt-wrap-0.3.0-2.fc25 failed!\n')
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_updateid(self, call, send_request):
        """
        Assert correct behavior with the --updateid flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.download,
            ['--updateid', 'FEDORA-2017-c95b33872d', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'updates/', verb='GET',
            params={'updateid': 'FEDORA-2017-c95b33872d'})
        assert bindings_client.base_url == 'http://localhost:6543/'
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])


class TestComposeInfo:
    """
    This class tests the info_compose() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(client.bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSE_MUNCH)
    def test_successful_operation(self, send_request, __init__):
        """
        Assert that a successful compose info is handled properly.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.info_compose, ['EPEL-7', 'stable'])

        assert result.exit_code == 0
        assert compare_output(result.output, client_test_data.EXPECTED_COMPOSE_OUTPUT)
        calls = [
            mock.call('composes/EPEL-7/stable', verb='GET')
        ]
        assert send_request.mock_calls == calls
        __init__.assert_called_once_with(base_url=EXPECTED_DEFAULT_BASE_URL, staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/request', status=404,
                    msg='update not found'))
    def test_compose_not_found(self, send_request, __init__):
        """
        Assert that info_compose() transforms a bodhi.client.bindings.ComposeNotFound into a
        click.BadParameter so that the user gets a nice error message.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.info_compose, ['EPEL-7', 'stable'])

        assert result.exit_code == 2
        assert compare_output(
            result.output,
            ('Usage: info [OPTIONS] RELEASE REQUEST\n\n'
             'Error: Invalid value for RELEASE/REQUEST: Compose with '
             'request "stable" not found for release "EPEL-7"'))
        send_request.assert_called_once_with('composes/EPEL-7/stable', verb='GET')
        __init__.assert_called_once_with(base_url=EXPECTED_DEFAULT_BASE_URL, staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.info_compose,
            ['--url', 'http://localhost:6543', 'EPEL-7', 'stable']
        )

        assert result.exit_code == 0
        assert compare_output(result.output, client_test_data.EXPECTED_COMPOSE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'composes/EPEL-7/stable', verb='GET',
            ),
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'


class TestListComposes:
    """Test the list_composes() function."""
    @mock.patch.dict(client_test_data.EXAMPLE_COMPOSES_MUNCH,
                     {'composes': [client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0]]})
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSES_MUNCH, autospec=True)
    def test_single_compose(self, send_request):
        """Test without the -v flag."""
        runner = testing.CliRunner()

        result = runner.invoke(client.list_composes)

        assert result.exit_code == 0
        assert '*EPEL-7-stable  :   2 updates (requested)' in result.output
        assert ' EPEL-7-testing :   1 updates (requested)' not in result.output
        bodhi_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bodhi_client, 'composes/', verb='GET')

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSES_MUNCH, autospec=True)
    def test_short(self, send_request):
        """Test without the -v flag."""
        runner = testing.CliRunner()

        result = runner.invoke(client.list_composes)

        assert result.exit_code == 0
        assert '*EPEL-7-stable  :   2 updates (requested)' in result.output
        assert ' EPEL-7-testing :   1 updates (requested)' in result.output
        bodhi_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bodhi_client, 'composes/', verb='GET')

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSES_MUNCH, autospec=True)
    def test_verbose(self, send_request):
        """Test with the -v flag."""
        runner = testing.CliRunner()

        result = runner.invoke(client.list_composes, ['-v'])

        assert result.exit_code == 0
        assert '*EPEL-7-stable  :   2 updates (requested)' in result.output
        assert 'Content Type: rpm' in result.output
        assert 'Started: 2018-03-15 17:25:22' in result.output
        assert 'Updated: 2018-03-15 17:25:22' in result.output
        assert 'Updates:' in result.output
        assert 'FEDORA-EPEL-2018-50566f0a39: uwsgi-2.0.16-1.el7' in result.output
        assert 'FEDORA-EPEL-2018-328e2b8c27: qtpass-1.2.1-3.el7' in result.output
        assert 'FEDORA-EPEL-2018-32f78e466c: libmodulemd-1.1.0-1.el7' in result.output
        assert ' EPEL-7-testing :   1 updates (requested)' in result.output
        bodhi_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bodhi_client, 'composes/', verb='GET')


class TestNew:
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
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', '--autotime',
             'bodhi-2.2.4-1.el7', '--severity', 'urgent', '--notes', 'No description.',
             '--stable-days', 7])

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('unspecified', 'urgent')
        assert compare_output(result.output, expected_output)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': 'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': 'No description.', 'request': None, 'bugs': '',
                    'requirements': None, 'unstable_karma': None, 'file': None, 'notes_file': None,
                    'type': 'bugfix', 'severity': 'urgent', 'display_name': None, 'autotime': True,
                    'stable_days': 7
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

    @mock.patch.dict(client_test_data.EXAMPLE_UPDATE_MUNCH, {'severity': 'urgent'})
    @mock.patch.dict(os.environ, {'BODHI_URL': 'http://example.com/tests/'})
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_debug_flag(self, send_request):
        """Assert correct behavior with the --debug flag."""
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--debug', '--user', 'bowlofeggs', '--password', 's3kr3t',
             '--autokarma', 'bodhi-2.2.4-1.el7', '--severity', 'urgent', '--notes',
             'No description.'])

        assert result.exit_code == 0
        expected_output = 'No `errors` nor `decision` in the data returned\n' \
            + client_test_data.EXPECTED_UPDATE_OUTPUT.replace('unspecified', 'urgent')
        assert compare_output(result.output, expected_output)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': 'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': 'No description.', 'request': None,
                    'bugs': '', 'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': 'urgent',
                    'display_name': None, 'autotime': False,
                    'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

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
             '--url', 'http://localhost:6543', '--notes', 'No description.'])

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': 'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': 'No description.', 'request': None, 'bugs': '',
                    'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': None, 'display_name': None,
                    'autotime': False, 'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_file_flag(self, send_request):
        """
        Assert correct behavior with the --file flag.
        """
        runner = testing.CliRunner()
        with tempfile.NamedTemporaryFile() as update_file:
            update_file.write(UPDATE_FILE.encode('utf-8'))
            update_file.flush()

            result = runner.invoke(
                client.new,
                ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
                 '--file', update_file.name, '--url', 'http://example.com/tests'])

        assert result.exit_code == 0
        assert compare_output(result.output, client_test_data.EXPECTED_UPDATE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': True, 'stable_karma': '3', 'csrf_token': 'a_csrf_token',
                    'builds': 'fedora-workstation-backgrounds-1.1-1.fc26',
                    'autokarma': 'True', 'suggest': 'unspecified', 'notes': 'Initial Release',
                    'request': 'testing', 'bugs': '123456,43212',
                    'unstable_karma': '-3', 'type_': 'bugfix', 'type': 'bugfix',
                    'type': 'bugfix', 'severity': 'unspecified', 'display_name': 'fake update name'
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

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
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--notes', 'No description.'])

        assert result.exit_code == 0
        assert "This is a BodhiClientException message" in result.output

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
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--notes', 'No description.'])

        assert result.exit_code == 0
        assert "Traceback (most recent call last):" in result.output
        assert "Exception: This is an Exception message" in result.output

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
             '--bugs', '1234567', '--close-bugs', '--url', 'http://localhost:6543', '--notes',
             'No description.'])

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output + '\n')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': True, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': 'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': 'No description.', 'request': None,
                    'bugs': '1234567', 'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': None, 'display_name': None,
                    'autotime': False, 'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_display_name_flag(self, send_request):
        """
        Assert correct behavior with the --display-name flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--bugs', '1234567', '--display-name', 'fake display name', '--url',
             'http://localhost:6543', '--notes', 'No description.'])

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output + '\n')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': 'bodhi-2.2.4-1.el7', 'autokarma': True,
                    'suggest': None, 'notes': 'No description.', 'request': None,
                    'bugs': '1234567', 'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': None,
                    'display_name': 'fake display name', 'autotime': False, 'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_from_tag_flag(self, send_request):
        """
        Assert correct behavior with the --from-tag flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'fake_tag',
             '--bugs', '1234567', '--from-tag', '--url',
             'http://localhost:6543', '--notes', 'No description.'])

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output + '\n')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': None, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'autokarma': True, 'autotime': False, 'stable_days': None,
                    'suggest': None, 'notes': 'No description.', 'request': None,
                    'bugs': '1234567', 'requirements': None, 'unstable_karma': None, 'file': None,
                    'notes_file': None, 'type': 'bugfix', 'severity': None, 'display_name': None,
                    'from_tag': 'fake_tag'
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

    def test_from_tag_flag_multiple_tags(self):
        """
        Assert correct behavior with the --from-tag and multiple tags.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'fake tag',
             '--bugs', '1234567', '--from-tag', '--url',
             'http://localhost:6543', '--notes', 'No description.'])

        assert result.exit_code == 1
        assert result.output == 'ERROR: Can\'t specify more than one tag.\n'

    def test_new_update_without_notes(self):
        """
        Assert providing neither --notes-file nor --notes parameters to new update request
        results in an error.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', '--autokarma', 'bodhi-2.2.4-1.el7',
             '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ('ERROR: must specify at least one of --file,'
                                 ' --notes, or --notes-file\n')

    def test_new_security_update_with_unspecified_severity(self):
        """Assert not providing --severity to new security update request results in an error."""
        runner = testing.CliRunner()

        result = runner.invoke(
            client.new,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'bodhi-2.2.4-1.el7',
             '--notes', 'bla bla bla', '--type', 'security'])

        assert result.exit_code == 2
        assert result.output == (
            'Usage: new [OPTIONS] BUILDS_OR_TAG\n\nError: Invalid '
            'value for severity: must specify severity for a security update\n')


class TestPrintOverrideKojiHint:
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

        assert echo.call_count == 0
        assert c.send_request.call_count == 0


real_open = open


def fake_open_no_session_cache(*args, **kwargs):
    """Fake open so that it looks like we have no session cache."""
    if args[0] == fedora.client.openidbaseclient.b_SESSION_FILE:
        return mock.mock_open(read_data=b'{}')(*args, **kwargs)
    return real_open(*args, **kwargs)


class TestQuery:
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

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_QUERY_OUTPUT + '\n'
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'updateid': None, 'alias': None, 'approved_since': None,
                    'approved_before': None, 'status': None, 'locked': None,
                    'builds': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'releases': None,
                    'content_type': None, 'severity': None,
                    'submitted_since': None, 'submitted_before': None, 'suggest': None,
                    'request': None, 'bugs': None, 'staging': False, 'modified_since': None,
                    'modified_before': None, 'pushed': None, 'pushed_since': None,
                    'pushed_before': None, 'user': None, 'critpath': None, 'packages': None,
                    'type': None, 'rows_per_page': None, 'page': None, 'gating': None,
                    'from_side_tag': None,
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

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

        assert result.exit_code == 0
        assert result.output == client_test_data.EXAMPLE_QUERY_OUTPUT_MULTI
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'updates/', verb='GET',
            params={
                'updateid': None, 'alias': None, 'approved_since': None,
                'approved_before': None, 'status': None, 'locked': None,
                'builds': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'releases': None,
                'content_type': None, 'severity': None,
                'submitted_since': None, 'submitted_before': None, 'suggest': None,
                'request': None, 'bugs': None, 'staging': False, 'modified_since': None,
                'modified_before': None, 'pushed': None, 'pushed_since': None,
                'pushed_before': None, 'user': None, 'critpath': None, 'packages': None,
                'type': None, 'rows_per_page': None, 'page': None, 'gating': None,
                'from_side_tag': None})

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

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_QUERY_OUTPUT.replace('example.com/tests',
                                                                         'localhost:6543')
        assert result.output == expected_output + '\n'
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'updateid': None, 'alias': None, 'approved_since': None,
                    'approved_before': None, 'status': None, 'locked': None,
                    'builds': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'releases': None,
                    'content_type': None, 'severity': None,
                    'submitted_since': None, 'submitted_before': None, 'suggest': None,
                    'request': None, 'bugs': None, 'staging': False, 'modified_since': None,
                    'modified_before': None, 'pushed': None, 'pushed_since': None,
                    'pushed_before': None, 'user': None, 'critpath': None, 'packages': None,
                    'type': None, 'rows_per_page': None, 'page': None, 'gating': None,
                    'from_side_tag': None,
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    def test_query_mine_flag_username_unset(self, mock_input, send_request):
        """Assert that we use init_username if --user is not given."""
        mock_input.return_value = 'dudemcpants'

        with mock.patch.dict('os.environ'):
            with mock.patch('builtins.open', create=True) as mock_open:
                mock_open.side_effect = fake_open_no_session_cache
                runner = testing.CliRunner()
                res = runner.invoke(client.query, ['--mine'])

        assert res.exit_code == 0
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'updateid': None, 'alias': None, 'approved_since': None,
                    'approved_before': None, 'status': None, 'locked': None,
                    'builds': None, 'releases': None,
                    'content_type': None, 'severity': None, 'submitted_since': None,
                    'submitted_before': None, 'suggest': None, 'request': None, 'bugs': None,
                    'staging': False, 'modified_since': None, 'modified_before': None,
                    'pushed': None, 'pushed_since': None, 'pushed_before': None,
                    'user': 'dudemcpants', 'critpath': None, 'packages': None,
                    'type': None, 'rows_per_page': None, 'page': None, 'gating': None,
                    'from_side_tag': None,
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        # Before F31 the file was opened in binary mode, and then it changed.
        # Only check the path.
        assert mock_open.call_count
        first_args = [args[0][0] for args in mock_open.call_args_list]
        assert fedora.client.openidbaseclient.b_SESSION_FILE in first_args

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

        assert result.exit_code == 0
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'updateid': None, 'alias': None, 'approved_since': None,
                    'approved_before': None, 'status': None, 'locked': None,
                    'builds': None, 'releases': None,
                    'content_type': None, 'severity': None,
                    'submitted_since': None, 'submitted_before': None, 'suggest': None,
                    'request': None, 'bugs': None, 'staging': False, 'modified_since': None,
                    'modified_before': None, 'pushed': None, 'pushed_since': None,
                    'pushed_before': None, 'user': None, 'critpath': None, 'packages': None,
                    'type': None, 'rows_per_page': 10, 'page': None, 'gating': None,
                    'from_side_tag': None,
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

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

        assert result.exit_code == 0
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', verb='GET',
                params={
                    'updateid': None, 'alias': None, 'approved_since': None,
                    'approved_before': None, 'status': None, 'locked': None,
                    'builds': None, 'releases': None,
                    'content_type': None, 'severity': None,
                    'submitted_since': None, 'submitted_before': None, 'suggest': None,
                    'request': None, 'bugs': None, 'staging': False, 'modified_since': None,
                    'modified_before': None, 'pushed': None, 'pushed_since': None,
                    'pushed_before': None, 'user': None, 'critpath': None, 'packages': None,
                    'type': None, 'rows_per_page': None, 'page': 5, 'gating': None,
                    'from_side_tag': None,
                },
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls


class TestQueryBuildrootOverrides:
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

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_QUERY_OVERRIDES_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'overrides/', verb='GET',
            params={'user': 'bowlofeggs'})
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    def test_queryoverrides_mine_flag_username_unset(self, mock_input, send_request):
        """Assert that we use init_username if --user is not given."""
        mock_input.return_value = 'dudemcpants'

        with mock.patch.dict('os.environ'):
            with mock.patch('builtins.open', create=True) as mock_open:
                mock_open.side_effect = fake_open_no_session_cache
                runner = testing.CliRunner()
                res = runner.invoke(client.query_buildroot_overrides, ['--mine'])

        assert res.exit_code == 0
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'overrides/', verb='GET', params={'user': 'dudemcpants'}
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        # Before F31 the file was opened in binary mode, and then it changed.
        # Only check the path.
        assert mock_open.call_count
        first_args = [args[0][0] for args in mock_open.call_args_list]
        assert fedora.client.openidbaseclient.b_SESSION_FILE in first_args

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

        assert result.exit_code == 0
        assert result.output == (client_test_data.EXPECTED_OVERRIDES_OUTPUT
                                 + "1 overrides found (1 shown)\n")
        bindings_client = send_request.mock_calls[0][1][0]
        assert send_request.call_count == 2
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'overrides/',
                                                       verb='GET',
                                                       params={'builds': 'bodhi-2.10.1-1.fc25'})
        assert send_request.mock_calls[1] == mock.call(bindings_client,
                                                       'releases/',
                                                       verb='GET',
                                                       params={'ids': [15]})

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

        assert result.exit_code == 0
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

        assert result.exit_code == 0
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'overrides/', verb='GET',
            params={'page': 5})


@mock.patch.dict(os.environ, {'BODHI_OPENID_API': 'https://id.example.com/api/v1/'})
class TestRequest:
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

        assert result.exit_code == 0
        assert compare_output(result.output, client_test_data.EXPECTED_UPDATE_OUTPUT)
        calls = [
            mock.call(
                'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
                data={
                    'csrf_token': 'a_csrf_token', 'request': 'revoke',
                    'update': 'bodhi-2.2.4-1.el7'
                }
            ),
            mock.call(
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        __init__.assert_called_once_with(
            base_url=EXPECTED_DEFAULT_BASE_URL, username='some_user', password='s3kr3t',
            staging=False, openid_api='https://id.example.com/api/v1/')

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

        assert result.exit_code == 2
        assert compare_output(
            result.output,
            ('Usage: request [OPTIONS] UPDATE STATE\n\nError: Invalid value for UPDATE: Update not'
             ' found: bodhi-2.2.4-99.el7\n'))
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-99.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-99.el7'})
        __init__.assert_called_once_with(
            base_url=EXPECTED_DEFAULT_BASE_URL, username='some_user', password='s3kr3t',
            staging=False, openid_api='https://id.example.com/api/v1/')

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

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output)
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/bodhi-2.2.4-99.el7/request', verb='POST', auth=True,
                data={
                    'csrf_token': 'a_csrf_token', 'request': 'revoke',
                    'update': 'bodhi-2.2.4-99.el7'
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'


class TestSaveBuildrootOverrides:
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
             'http://localhost:6543/', '--no-wait'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_OVERRIDES_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = send_request.mock_calls[0][2]['data']['expiration_date']
        assert (datetime.datetime.utcnow() - expire_time) < datetime.timedelta(seconds=5)
        # There should be two calls to send_request(). The first to save the override, and the
        # second to find out the release tags so the koji wait-repo hint can be printed.
        assert send_request.call_count == 2
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'overrides/',
                                                       verb='POST',
                                                       auth=True,
                                                       data={'expiration_date': expire_time,
                                                             'notes': 'No explanation given...',
                                                             'nvr': 'js-tag-it-2.0-1.fc25',
                                                             'csrf_token': 'a_csrf_token'})
        assert send_request.mock_calls[1] == mock.call(bindings_client,
                                                       'releases/',
                                                       verb='GET',
                                                       params={'ids': [15]})
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_wait_default(self, call, send_request):
        """Assert that the --wait flag is the default."""
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        send_request.side_effect = _send_request

        result = runner.invoke(
            client.save_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25'])

        assert result.exit_code == 0
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'.format(
                client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT))
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_wait_flag(self, call, send_request):
        """
        Assert correct behavior with the --wait flag.
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
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25', '--wait'])

        assert result.exit_code == 0
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'.format(
                client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT))
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=42)
    def test_wait_flag_fail(self, call, send_request):
        """
        Assert correct behavior when the command execution due to --wait flag fails.
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
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25', '--wait'])

        assert result.exit_code == 42
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'
            'WARNING: ensuring active override failed for js-tag-it-2.0-1.fc25\n')
        expected_output = expected_output.format(client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT)
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_create_multiple_overrides(self, send_request):
        """
        Assert correct behavior when user creates multiple overrides.
        """
        runner = testing.CliRunner()

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            response = client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH
            del response['total']
            return response

        send_request.side_effect = _send_request
        expected_output = client_test_data.EXPECTED_QUERY_OVERRIDES_OUTPUT
        expected_output = expected_output.replace("11 overrides found (11 shown)\n", "")

        overrides_nvrs = [
            'nodejs-grunt-wrap-0.3.0-2.fc25',
            'python-pyramid-1.5.6-3.el7',
            'erlang-esip-1.0.8-1.fc25',
            'erlang-stun-1.0.7-1.fc25',
            'erlang-iconv-1.0.2-1.fc25',
            'erlang-stringprep-1.0.6-1.fc25',
            'erlang-fast_tls-1.0.7-1.fc25',
            'erlang-fast_yaml-1.0.6-1.fc25',
            'erlang-fast_xml-1.1.15-1.fc25',
            'python-fedmsg-atomic-composer-2016.3-1.el7',
            'python-fedmsg-atomic-composer-2016.3-1.fc24',
        ]

        overrides_nvrs_str = " ".join(overrides_nvrs)

        result = runner.invoke(
            client.save_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', overrides_nvrs_str, '--url',
             'http://localhost:6543/', '--no-wait'])

        assert result.exit_code == 0
        assert result.output == expected_output
        bindings_client = send_request.mock_calls[0][1][0]
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = send_request.mock_calls[0][2]['data']['expiration_date']
        assert (datetime.datetime.utcnow() - expire_time) < datetime.timedelta(seconds=5)
        # There should be one calls to send_request().
        assert send_request.call_count == 1
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'overrides/',
                                                       verb='POST',
                                                       auth=True,
                                                       data={'expiration_date': expire_time,
                                                             'notes': 'No explanation given...',
                                                             'nvr': overrides_nvrs_str,
                                                             'csrf_token': 'a_csrf_token'})
        assert bindings_client.base_url == 'http://localhost:6543/'


class TestWarnIfUrlOrOpenidAndStagingSet:
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
        param = mock.MagicMock()
        param.name = 'url'

        result = client._warn_if_url_or_openid_and_staging_set(
            ctx, param, 'http://localhost:6543')

        assert result == 'http://localhost:6543'
        assert echo.call_count == 0

    @mock.patch('bodhi.client.click.echo')
    def test_staging_missing(self, echo):
        """
        Nothing should be printed when staging is not present in the context.
        """
        ctx = mock.MagicMock()
        ctx.params = {}
        param = mock.MagicMock()
        param.name = 'url'

        result = client._warn_if_url_or_openid_and_staging_set(
            ctx, param, 'http://localhost:6543')

        assert result == 'http://localhost:6543'
        assert echo.call_count == 0

    @mock.patch('bodhi.client.click.echo')
    def test_staging_true(self, echo):
        """
        A warning should be printed to stderr when staging is True and url/openid provided.
        """
        # Check url param when staging is set
        ctx = mock.MagicMock()
        ctx.params = {'staging': True}
        param = mock.MagicMock()
        param.name = 'url'

        result = client._warn_if_url_or_openid_and_staging_set(
            ctx, param, 'http://localhost:6543')

        assert result == 'http://localhost:6543'
        echo.assert_called_once_with(
            '\nWarning: url and staging flags are both set. url will be ignored.\n', err=True)

        # Check staging param when url is set
        echo.reset_mock()
        ctx = mock.MagicMock()
        ctx.params = {'url': 'fake_url'}
        param = mock.MagicMock()
        param.name = 'staging'

        result = client._warn_if_url_or_openid_and_staging_set(ctx, param, True)

        assert result
        echo.assert_called_once_with(
            '\nWarning: url and staging flags are both set. url will be ignored.\n', err=True)

        # Check staging param when openid_api is set
        echo.reset_mock()
        ctx = mock.MagicMock()
        ctx.params = {'openid_api': 'fake_openid'}
        param = mock.MagicMock()
        param.name = 'staging'

        result = client._warn_if_url_or_openid_and_staging_set(ctx, param, True)

        assert result
        echo.assert_called_once_with(
            '\nWarning: openid_api and staging flags are both set. openid_api will be ignored.\n',
            err=True
        )


class TestEdit:
    """
    This class tests the edit() function.
    """

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_bugs_flag(self, send_request, query):
        """Assert that the --bugs flag is handled properly."""
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--bugs', '1234,5678'])

        assert result.exit_code == 0
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': ['nodejs-grunt-wrap-0.3.0-2.fc25'],
                    'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                    'suggest': 'unspecified', 'notes': 'New package.',
                    'notes_file': None, 'request': None, 'unstable_karma': -3,
                    'bugs': '1234,5678', 'requirements': '', 'type': 'newpackage',
                    'severity': 'low', 'display_name': None, 'autotime': False,
                    'stable_days': None}),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET')]
        assert send_request.mock_calls == calls

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
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--severity', 'low',
                          '--notes', 'Updated package.'])

        assert result.exit_code == 0
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': ['nodejs-grunt-wrap-0.3.0-2.fc25'],
                    'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                    'suggest': 'unspecified', 'notes': 'Updated package.',
                    'notes_file': None, 'request': None, 'unstable_karma': -3,
                    'bugs': '1420605', 'requirements': '', 'type': 'newpackage',
                    'severity': 'low', 'display_name': None, 'autotime': False, 'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

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
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'this is an edited note',
                          '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': ['nodejs-grunt-wrap-0.3.0-2.fc25'],
                    'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                    'suggest': 'unspecified', 'notes': 'this is an edited note',
                    'notes_file': None, 'request': None, 'severity': 'low',
                    'bugs': '1420605', 'requirements': '', 'unstable_karma': -3,
                    'type': 'newpackage', 'display_name': None, 'autotime': False,
                    'stable_days': None,
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

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
                client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                              '--password', 's3kr3t', '--notes-file', 'notefile.txt',
                              '--url', 'http://localhost:6543'])

            assert result.exit_code == 0
            bindings_client = query.mock_calls[0][1][0]
            query.assert_called_with(
                bindings_client, updateid='FEDORA-2017-c95b33872d')
            bindings_client = send_request.mock_calls[0][1][0]
            calls = [
                mock.call(
                    bindings_client, 'updates/', auth=True, verb='POST',
                    data={
                        'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                        'staging': False, 'builds': ['nodejs-grunt-wrap-0.3.0-2.fc25'],
                        'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                        'suggest': 'unspecified', 'notes': 'This is a --notes-file note!',
                        'notes_file': 'notefile.txt', 'request': None, 'severity': 'low',
                        'bugs': '1420605', 'requirements': '', 'unstable_karma': -3,
                        'type': 'newpackage', 'display_name': None, 'autotime': False,
                        'stable_days': None
                    }
                ),
                mock.call(
                    bindings_client,
                    'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                    verb='GET'
                )
            ]
            assert send_request.mock_calls == calls
            assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_addbuilds_removebuilds(self, send_request, query):
        """
        Assert that a addbuilds and removebuilds are properly handled in a successful updates
        edit request.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'add and remove builds',
                          '--addbuilds', 'tar-1.29-4.fc25,nedit-5.7-1.fc25',
                          '--removebuilds', 'nodejs-grunt-wrap-0.3.0-2.fc25',
                          '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid=u'FEDORA-2017-c95b33872d')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'display_name': None,
                    'builds': ['tar-1.29-4.fc25', 'nedit-5.7-1.fc25'],
                    'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                    'suggest': u'unspecified', 'notes': u'add and remove builds',
                    'notes_file': None, 'request': None, 'severity': u'low',
                    'bugs': '1420605', 'requirements': u'', 'unstable_karma': -3,
                    'type': 'newpackage', 'autotime': False, 'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query', autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_from_tag_flag(self, send_request, query):
        """
        Assert correct behavior with the --from-tag flag.
        """
        data = client_test_data.EXAMPLE_QUERY_MUNCH.copy()
        data.updates[0]['from_tag'] = 'fake_tag'
        data.updates[0]['release']['composed_by_bodhi'] = False
        query.return_value = data
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--from-tag',
                          '--notes', 'Updated package.',
                          '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                    'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                    'suggest': 'unspecified', 'notes': 'Updated package.',
                    'notes_file': None, 'request': None, 'unstable_karma': -3,
                    'bugs': '1420605', 'requirements': '', 'type': 'newpackage',
                    'severity': u'low', 'display_name': None, 'autotime': False,
                    'stable_days': None, 'from_tag': 'fake_tag',
                    'staging': False,
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    def test_from_tag_flag_no_tag(self, query):
        """
        Assert --from-tag bails out if the update wasn't created from a tag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--from-tag',
                          '--notes', 'Updated package.',
                          '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ("ERROR: This update was not created from a tag."
                                 " Please remove --from_tag and try again.\n")
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query', autospec=True)
    def test_from_tag_addbuilds(self, query):
        """
        Assert --from-tag can't be used with --addbuilds.
        """
        data = client_test_data.EXAMPLE_QUERY_MUNCH.copy()
        data.updates[0]['from_tag'] = 'fake_tag'
        query.return_value = data

        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--from-tag',
                          '--addbuilds', 'tar-1.29-4.fc25,nedit-5.7-1.fc25',
                          '--notes', 'Updated package.',
                          '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ("ERROR: The --from-tag option can't be used together with"
                                 " --addbuilds or --removebuilds.\n")
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query', autospec=True)
    def test_from_tag_removebuilds(self, query):
        """
        Assert --from-tag can't be used with --removebuilds.
        """
        data = client_test_data.EXAMPLE_QUERY_MUNCH.copy()
        data.updates[0]['from_tag'] = 'fake_tag'
        query.return_value = data

        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--from-tag',
                          '--removebuilds', 'nodejs-grunt-wrap-0.3.0-2.fc25',
                          '--notes', 'Updated package.',
                          '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ("ERROR: The --from-tag option can't be used together with"
                                 " --addbuilds or --removebuilds.\n")
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')

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

            assert result.exit_code == 1
            assert result.output == 'ERROR: Cannot specify --notes and --notes-file\n'

    def test_wrong_update_id_argument(self):
        """
        Assert that an error is given if the edit update argument given is not an update id.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['drupal7-i18n-1.17-1', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'this is an edited note',
                          '--url', 'http://localhost:6543'])
        assert result.exit_code == 2
        # Click 7.0 capitalizes UPDATE, and < 7 does not.
        # Click <= 7.0 uses " while > 7 uses '
        click_ver = [int(n) for n in click.__version__.split('.')]
        if click_ver < [7, 0]:
            label = '"update"'
        elif click_ver == [7, 0]:
            label = '"UPDATE"'
        else:
            label = "'UPDATE'"
        expected = f'Usage: edit [OPTIONS] UPDATE\n\n' \
                   f'Error: Invalid value for {label}: ' \
                   f'Please provide an Update ID\n'

        assert result.output == expected

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
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'testing required tasks',
                          '--requirements', 'dist.depcheck dist.rpmdeplint', '--url',
                          'http://localhost:6543'])

        assert result.exit_code == 0
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': ['nodejs-grunt-wrap-0.3.0-2.fc25'],
                    'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                    'suggest': 'unspecified', 'notes': 'testing required tasks',
                    'notes_file': None, 'request': None, 'severity': 'low',
                    'bugs': '1420605', 'unstable_karma': -3, 'display_name': None,
                    'requirements': 'dist.depcheck dist.rpmdeplint', 'type': 'newpackage',
                    'autotime': False, 'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls
        assert bindings_client.base_url == 'http://localhost:6543/'

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
                          '--password', 's3kr3t', '--notes', 'No description.'])

        assert result.exit_code == 0
        assert "This is a BodhiClientException message" in result.output

    @mock.patch.dict(client_test_data.EXAMPLE_QUERY_MUNCH['updates'][0], {'bugs': []})
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH, autospec=True)
    def test_edit_bugless_update_without_bugs_param(self, send_request, query):
        """Test editing an update with no bugs, without passing '--bugs' to it."""
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-c95b33872d', '--user', 'bowlofeggs',
                          '--password', 's3kr3t'])

        assert result.exit_code == 0
        bindings_client = query.mock_calls[0][1][0]
        query.assert_called_with(
            bindings_client, updateid='FEDORA-2017-c95b33872d')
        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client, 'updates/', auth=True, verb='POST',
                data={
                    'close_bugs': False, 'stable_karma': 3, 'csrf_token': 'a_csrf_token',
                    'staging': False, 'builds': ['nodejs-grunt-wrap-0.3.0-2.fc25'],
                    'autokarma': False, 'edited': 'FEDORA-2017-c95b33872d',
                    'suggest': 'unspecified', 'notes': 'New package.', 'display_name': None,
                    'notes_file': None, 'request': None, 'severity': 'low',
                    'bugs': '', 'requirements': '', 'unstable_karma': -3, 'type': 'newpackage',
                    'autotime': False, 'stable_days': None
                }
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.query',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    def test_edit_security_update_with_unspecified_severity(self, query):
        """Assert 'unspecified' severity while editing a security update results in an error."""
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit, ['FEDORA-2017-cc8582d738', '--user', 'bowlofeggs',
                          '--password', 's3kr3t', '--notes', 'this is an edited note',
                          '--type', 'security', '--severity', 'unspecified'])

        assert result.exit_code == 2
        assert result.output == ('Usage: edit [OPTIONS] UPDATE\n\nError: Invalid '
                                 'value for severity: must specify severity for '
                                 'a security update\n')


class TestEditBuildrootOverrides:
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

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_EXPIRED_OVERRIDES_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = send_request.mock_calls[0][2]['data']['expiration_date']
        assert (datetime.datetime.utcnow() - expire_time) < datetime.timedelta(seconds=5)
        send_request.assert_called_once_with(
            bindings_client, 'overrides/', verb='POST', auth=True,
            data={
                'expiration_date': expire_time, 'notes': 'This is an expired override',
                'nvr': 'js-tag-it-2.0-1.fc25', 'edited': 'js-tag-it-2.0-1.fc25',
                'csrf_token': 'a_csrf_token', 'expired': True})
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=0)
    def test_wait_flag(self, call, send_request):
        """
        Assert correct behavior with the --wait flag.
        """
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        send_request.side_effect = _send_request

        result = runner.invoke(
            client.edit_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25', '--wait'])

        assert result.exit_code == 0
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'.format(
                client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT))
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    @mock.patch('bodhi.client.subprocess.call', return_value=24)
    def test_wait_flag_fail(self, call, send_request):
        """
        Assert correct behavior when the command execution due to --wait flag fails.
        """
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        send_request.side_effect = _send_request

        result = runner.invoke(
            client.edit_buildroot_overrides,
            ['--user', 'bowlofeggs', '--password', 's3kr3t', 'js-tag-it-2.0-1.fc25', '--wait'])

        assert result.exit_code == 24
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'
            'WARNING: ensuring active override failed for js-tag-it-2.0-1.fc25\n')
        expected_output = expected_output.format(client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT)
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)


class TestCreate:
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
            ['--name', 'F27', '--url', 'http://localhost:6543', '--user', 'bowlofeggs',
             '--password', 's3kr3t'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': None, 'csrf_token': 'a_csrf_token', 'staging': False, 'name': 'F27',
                  'testing_tag': None, 'pending_stable_tag': None, 'long_name': None, 'state': None,
                  'version': None, 'override_tag': None, 'branch': None, 'id_prefix': None,
                  'pending_testing_tag': None, 'pending_signing_tag': None, 'stable_tag': None,
                  'candidate_tag': None, 'mail_template': None, 'composed_by_bodhi': True,
                  'create_automatic_updates': False, 'package_manager': None,
                  'testing_repository': None})
        assert bindings_client.base_url == 'http://localhost:6543/'

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
            ['--name', 'F27', '--url', 'http://localhost:6543', '--user', 'bowlofeggs',
             '--password', 's3kr3t'])

        assert result.exit_code == 1
        assert result.output == "ERROR: an error was encountered... :(\n"


class TestEditRelease:
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
             'http://localhost:6543', '--user', 'bowlofeggs', '--password', 's3kr3t'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        assert send_request.call_count == 2
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'releases/F27',
                                                       verb='GET',
                                                       auth=True)
        assert send_request.mock_calls[1] == mock.call(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'staging': False,
                  'name': 'F27', 'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                  'pending_stable_tag': 'f27-updates-pending',
                  'pending_signing_tag': 'f27-signing-pending',
                  'long_name': 'Fedora 27, the Greatest Fedora!', 'state': 'pending',
                  'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                  'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                  'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate',
                  'mail_template': 'fedora_errata_template', 'composed_by_bodhi': True,
                  'create_automatic_updates': False, 'package_manager': 'unspecified',
                  'testing_repository': None})
        assert bindings_client.base_url == 'http://localhost:6543/'

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
             'http://localhost:6543', '--user', 'bowlofeggs', '--password', 's3kr3t'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        assert send_request.call_count == 2
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'releases/F27',
                                                       verb='GET',
                                                       auth=True)
        assert send_request.mock_calls[1] == mock.call(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'staging': False,
                  'name': 'fedora27', 'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                  'pending_stable_tag': 'f27-updates-pending',
                  'pending_signing_tag': 'f27-signing-pending',
                  'long_name': 'Fedora 27', 'state': 'pending',
                  'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                  'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                  'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate',
                  'mail_template': 'fedora_errata_template', 'composed_by_bodhi': True,
                  'create_automatic_updates': False, 'package_manager': 'unspecified',
                  'testing_repository': None})

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
             'http://localhost:6543', '--user', 'bowlofeggs', '--password', 's3kr3t'])

        assert result.output == "ERROR: Please specify the name of the release to edit\n"
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
             'http://localhost:6543', '--user', 'bowlofeggs', '--password', 's3kr3t'])

        assert result.exit_code == 1
        assert result.output == "ERROR: an error was encountered... :(\n"

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_edit_mail_template(self, send_request):
        """
        Assert correct behavior while editing 'mail_template' name.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_release,
            ['--name', 'F27', '--mail-template', 'edited_fedora_errata_template'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        assert send_request.call_count == 2
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'releases/F27',
                                                       verb='GET',
                                                       auth=True)
        assert send_request.mock_calls[1] == mock.call(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'staging': False,
                  'name': 'F27', 'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                  'pending_stable_tag': 'f27-updates-pending',
                  'pending_signing_tag': 'f27-signing-pending',
                  'long_name': 'Fedora 27', 'state': 'pending',
                  'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                  'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                  'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate',
                  'mail_template': 'edited_fedora_errata_template', 'composed_by_bodhi': True,
                  'create_automatic_updates': False, 'package_manager': 'unspecified',
                  'testing_repository': None})

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_edit_not_composed_by_bodhi_flag(self, send_request):
        """
        Assert correct behavior while editing 'composed_by_bodhi' flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_release,
            ['--name', 'F27', '--not-composed-by-bodhi'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        assert send_request.call_count == 2
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'releases/F27',
                                                       verb='GET',
                                                       auth=True)
        assert send_request.mock_calls[1] == mock.call(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'staging': False,
                  'name': 'F27', 'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                  'pending_stable_tag': 'f27-updates-pending',
                  'pending_signing_tag': 'f27-signing-pending',
                  'long_name': 'Fedora 27', 'state': 'pending',
                  'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                  'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                  'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate',
                  'mail_template': 'fedora_errata_template',
                  'composed_by_bodhi': False, 'package_manager': 'unspecified',
                  'testing_repository': None, 'create_automatic_updates': False})

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_edit_create_automatic_updates_flag(self, send_request):
        """
        Assert correct behavior while editing 'created_automatic_updates' flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.edit_release,
            ['--name', 'F27', '--create-automatic-updates'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        bindings_client = send_request.mock_calls[0][1][0]
        assert send_request.call_count == 2
        assert send_request.mock_calls[0] == mock.call(bindings_client,
                                                       'releases/F27',
                                                       verb='GET',
                                                       auth=True)
        assert send_request.mock_calls[1] == mock.call(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'staging': False,
                  'name': 'F27', 'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                  'pending_stable_tag': 'f27-updates-pending',
                  'pending_signing_tag': 'f27-signing-pending',
                  'long_name': 'Fedora 27', 'state': 'pending',
                  'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                  'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                  'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate',
                  'mail_template': 'fedora_errata_template',
                  'composed_by_bodhi': True, 'create_automatic_updates': True,
                  'package_manager': 'unspecified', 'testing_repository': None})


class TestInfo:
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

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT.replace('Saved r', 'R')
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bindings_client, 'releases/F27', verb='GET',
                                             auth=False)
        assert bindings_client.base_url == 'http://localhost:6543/'

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

        assert result.exit_code == 1
        assert result.output == "ERROR: an error was encountered... :(\n"


class TestListReleases:
    """
    Test the list_releases() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH_NO_ARCHIVED,
                autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.list_releases, ['--url', 'http://localhost:6543'])

        expected_output = '{}\n{}\n{}'.format(
            client_test_data.EXPECTED_PENDING_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_CURRENT_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_FROZEN_RELEASES_LIST_OUTPUT,
        )

        assert result.exit_code == 0
        assert result.output == expected_output
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'releases/', params={
                'rows_per_page': None, 'page': None, 'exclude_archived': True
            }, verb='GET'
        )
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH_NO_ARCHIVED,
                autospec=True)
    def test_pagination(self, send_request):
        """
        Assert correct behavior using pagination.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.list_releases, ['--url', 'http://localhost:6543', '--rows', 4, '--page', 1]
        )

        expected_output = '{}\n{}\n{}'.format(
            client_test_data.EXPECTED_PENDING_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_CURRENT_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_FROZEN_RELEASES_LIST_OUTPUT,
        )

        assert result.exit_code == 0
        assert result.output == expected_output
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'releases/', params={
                'rows_per_page': 4, 'page': 1, 'exclude_archived': True
            }, verb='GET'
        )
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_RELEASE_MUNCH_WITH_ARCHIVED,
                autospec=True)
    def test_display_archived_flag(self, send_request):
        """
        Assert correct behavior with the --display-archived flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.list_releases, ['--url', 'http://localhost:6543', '--display-archived']
        )

        expected_output = '{}\n{}\n{}'.format(
            client_test_data.EXPECTED_PENDING_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_ARCHIVED_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_CURRENT_RELEASES_LIST_OUTPUT,
        )

        assert result.exit_code == 0
        assert result.output == expected_output
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'releases/', params={
                'rows_per_page': None, 'page': None, 'exclude_archived': False
            }, verb='GET'
        )
        assert bindings_client.base_url == 'http://localhost:6543/'

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value={"errors": [{"description": "an error was encountered... :("}]},
                autospec=True)
    def test_list_releases_with_errors(self, send_request):
        """
        Assert errors are printed if returned back in the request
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.list_releases, ['--url', 'http://localhost:6543'])

        assert result.exit_code == 2
        assert result.output == "an error was encountered... :(\n"
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'releases/', params={
                'rows_per_page': None, 'page': None, 'exclude_archived': True
            }, verb='GET'
        )
        assert bindings_client.base_url == 'http://localhost:6543/'


class TestPrintReleasesList:
    """
    Test the print_releases_list() function
    """
    @mock.patch('bodhi.client.click.echo')
    def test_only_pending_state(self, echo):
        """Assert that only release with pending state is printed ."""
        releases = [{"state": "pending", "name": "test_name"}]

        client.print_releases_list(releases)

        assert echo.call_count == 2
        assert echo.mock_calls[0][1][0] == 'pending:'
        assert echo.mock_calls[1][1][0] == '  Name:                test_name'

    @mock.patch('bodhi.client.click.echo')
    def test_only_archived_state(self, echo):
        """Assert that only release with archived state is printed ."""
        releases = [{"state": "archived", "name": "test_name"}]

        client.print_releases_list(releases)

        assert echo.call_count == 2
        assert echo.mock_calls[0][1][0] == '\narchived:'
        assert echo.mock_calls[1][1][0] == '  Name:                test_name'

    @mock.patch('bodhi.client.click.echo')
    def test_only_current_state(self, echo):
        """Assert that only release with current state is printed ."""
        releases = [{"state": "current", "name": "test_name"}]

        client.print_releases_list(releases)

        assert echo.call_count == 2
        assert echo.mock_calls[0][1][0] == '\ncurrent:'
        assert echo.mock_calls[1][1][0] == '  Name:                test_name'


class TestHandleErrors:
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

        assert result.exit_code == 2
        assert result.output == "Pants Exception\n"

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

        assert result.exit_code == 1
        assert result.output == "Authentication failed: Check your FAS username & password\n"


class TestPrintResp:
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
        assert compare_output(result.output, expected_output)

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_total_missing_in_response(self, send_request):
        """If total is missing in the response, the x updates found (y shown) should not appear."""
        response = copy.deepcopy(client_test_data.EXAMPLE_QUERY_MUNCH)
        del response['total']
        send_request.return_value = response
        runner = testing.CliRunner()

        result = runner.invoke(client.query, ['--url', 'http://example.com/tests'])

        assert 'updates found' not in result.output

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

        assert result.output == "{'pants': 'pants'}\n"

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

        assert "\nCaveats:\nthis is a caveat\n" in result.output


class TestWaive:
    """
    Test the waive() function.
    """

    def test_waive_show_and_tests(self):
        """
        Assert we error if the user specifies --show and --test.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            [
                '--show', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543',
                '--test', 'foobar'
            ]
        )

        assert result.exit_code == 1
        assert result.output == (
            'ERROR: You can not list the unsatisfied requirements and waive them at '
            'the same time, please use either --show or --test=... but not both.\n')

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_QUERY_MUNCH, autospec=True)
    def test_waive_show_invalid_data_returned(self, send_request):
        """
        Assert we error correctly when the data returned by bodhi does not fit our expectations.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            ['--show', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == 'Could not retrieve the unsatisfied requirements from bodhi.\n'
        bindings_client = send_request.mock_calls[0][1][0]

        send_request.assert_called_once_with(
            bindings_client,
            'updates/nodejs-grunt-wrap-0.3.0-2.fc25/get-test-results',
            verb='GET'
        )

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_waive_show_with_errors(self, send_request):
        """
        Assert we display the proper error messages when we try to list the unsatisfied
        requirements and there are errors in the data returned.
        """
        send_request.return_value = munch.Munch({
            'errors': [
                munch.Munch({'description': 'Could not contact greenwave, error code was 500'}),
            ]
        })

        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            ['--show', 'FEDORA-2017-cc8582d738', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert result.output == (
            'One or more errors occurred while retrieving the unsatisfied requirements:\n'
            '  - Could not contact greenwave, error code was 500\n')

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_waive_show_successful_missing_req(self, send_request):
        """
        Assert we display the unsatisfied requirements when everything is fine.
        """
        send_request.return_value = munch.Munch({
            'decision': munch.Munch({
                'summary': 'Two missing tests',
                'unsatisfied_requirements': [
                    munch.Munch({
                        'subject_type': 'koji_build',
                        'scenario': None,
                        'testcase': 'dist.rpmdeplint',
                        'item': munch.Munch({
                            'item': 'python-arrow-0.8.0-5.fc28',
                            'type': 'koji_build'
                        }),
                        'subject_identifier': 'python-arrow-0.8.0-5.fc28',
                        'type': 'test-result-missing'
                    }),
                    munch.Munch({
                        'subject_type': 'koji_build',
                        'scenario': None,
                        'testcase': 'fedora-atomic-ci',
                        'item': munch.Munch({
                            'item': 'python-arrow-0.8.0-5.fc28',
                            'type': 'koji_build'
                        }),
                        'subject_identifier': 'python-arrow-0.8.0-5.fc28',
                        'type': 'test-result-missing'
                    }),
                ]
            }),
        })

        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            ['--show', 'FEDORA-2017-cc8582d738', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert result.output == (
            'CI status: Two missing tests\nMissing tests:\n'
            '  - dist.rpmdeplint\n'
            '  - fedora-atomic-ci\n')

    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_waive_show_successful_no_missing_req(self, send_request):
        """
        Assert we display the unsatisfied requirements when everything is fine but there
        are no unsatisfied requirements.
        """
        send_request.return_value = munch.Munch({
            'decision': munch.Munch({
                'summary': 'No tests required',
                'unsatisfied_requirements': []
            }),

        })

        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            ['--show', 'FEDORA-2017-cc8582d738', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert result.output == (
            'CI status: No tests required\n'
            'Missing tests: None\n')

    def test_waive_missing_comment(self):
        """
        Assert we error if the user is trying to waive some tests without specifying a comment.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            ['--test', 'dist.rpmdeplint', 'FEDORA-2017-cc8582d738',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 1
        assert result.output == ('ERROR: A comment is mandatory when waiving '
                                 'unsatisfied requirements\n')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_waive_all(self, send_request):
        """
        Assert we properly waive all missing requirements when asked.
        """
        send_request.side_effect = [
            client_test_data.EXAMPLE_QUERY_MUNCH,
            munch.Munch({
                'decision': munch.Munch({
                    'summary': 'All tests passed',
                    'unsatisfied_requirements': [],
                    'waivers': [],
                }),
            })
        ]
        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            ['--test', 'all', 'FEDORA-2017-c95b33872d', 'Expected errors',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert 'Waiving all unsatisfied requirements\n' in result.output
        assert 'CI Status: All tests passed\n' in result.output

        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/waive-test-results',
                auth=True,
                data={'comment': 'Expected errors', 'csrf_token': 'a_csrf_token',
                      'tests': None, 'update': 'FEDORA-2017-c95b33872d'},
                verb='POST',
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_waive_some(self, send_request):
        """
        Assert we properly waive some missing requirements.
        """
        send_request.side_effect = [
            client_test_data.EXAMPLE_QUERY_MUNCH,
            munch.Munch({
                'decision': munch.Munch({
                    'summary': 'All tests passed',
                    'unsatisfied_requirements': [],
                    'waivers': [],
                }),
            })
        ]
        runner = testing.CliRunner()

        result = runner.invoke(
            client.waive,
            ['--test', 'dist.rpmdeplint', '--test', 'fedora-atomic-ci',
             'FEDORA-2017-c95b33872d', 'Expected errors',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert ('Waiving unsatisfied requirements: dist.rpmdeplint, fedora-atomic-ci\n'
                in result.output)
        assert 'CI Status: All tests passed\n' in result.output

        bindings_client = send_request.mock_calls[0][1][0]
        calls = [
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/waive-test-results',
                auth=True,
                data={'comment': 'Expected errors', 'csrf_token': 'a_csrf_token',
                      'tests': ('dist.rpmdeplint', 'fedora-atomic-ci'),
                      'update': 'FEDORA-2017-c95b33872d'},
                verb='POST',
            ),
            mock.call(
                bindings_client,
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert send_request.mock_calls == calls


class TestTriggerTests:
    """
    Test the trigger_tests() function.
    """

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request', autospec=True)
    def test_trigger_success(self, send_request):
        """
        Assert we properly trigger tests for updated.
        """
        send_request.return_value = munch.Munch({
            'decision': munch.Munch({
                'summary': 'Tests triggered',
            }),

        })
        runner = testing.CliRunner()

        result = runner.invoke(
            client.trigger_tests,
            ['FEDORA-2017-c95b33872d',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert "Tests triggered" in result.output

        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client,
            'updates/FEDORA-2017-c95b33872d/trigger-tests',
            auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'FEDORA-2017-c95b33872d'},
            verb='POST')
