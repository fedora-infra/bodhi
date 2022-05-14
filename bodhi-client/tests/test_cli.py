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
from datetime import date, datetime, timedelta
from unittest import mock
import copy
import os
import platform
import tempfile

from click import testing
from requests import HTTPError
import click
import munch
import pytest

from bodhi.client import bindings, cli, constants

from . import fixtures as client_test_data
from .utils import build_response, compare_output


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


EXAMPLE_QUERY_MUNCH_MULTI_BUILDS = copy.deepcopy(client_test_data.EXAMPLE_QUERY_MUNCH)
EXAMPLE_QUERY_MUNCH_MULTI_BUILDS.updates[0]['builds'].append({
    'epoch': 0,
    'nvr': 'nodejs-pants-0.3.0-2.fc25',
    'signed': True
})


@pytest.fixture
def mocked_client_class(mocker):
    class TestBodhiClient(bindings.BodhiClient):
        instances = []

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.csrf_token = "a_csrf_token"
            TestBodhiClient.instances.append(self)

        _build_oidc_client = mock.Mock(name="_build_oidc_client")
        send_request = mock.Mock(name="send_request")

    mocker.patch("bodhi.client.bindings.BodhiClient", side_effect=TestBodhiClient)
    return TestBodhiClient


class TestComment:
    """
    Test the comment() function.
    """

    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_COMMENT_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.comment,
            [
                'nodejs-grunt-wrap-0.3.0-2.fc25', 'After installing this I found $100.',
                '--url', 'http://localhost:6543', '--karma', '1'
            ]
        )

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_COMMENT_OUTPUT
        mocked_client_class.send_request.assert_called_once_with(
            'comments/', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'text': 'After installing this I found $100.',
                  'update': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'karma': 1})


class TestDownload:
    """
    Test the download() function.
    """

    def test_url_flag(self, mocked_client_class, mocker):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        mocked_client_class.send_request.assert_called_once_with(
            'updates/', verb='GET',
            params={'builds': 'nodejs-grunt-wrap-0.3.0-2.fc25'})
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

    def test_arch_flag(self, mocked_client_class, mocker):
        """
        Assert correct behavior with the --arch flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--arch', 'x86_64'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch=x86_64',
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

    def test_arch_all_flag(self, mocked_client_class, mocker):
        """
        Assert correct behavior with --arch all flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--arch', 'all'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_called_once_with([
            'koji', 'download-build', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

    def test_debuginfo_flag(self, mocked_client_class, mocker):
        """
        Assert correct behavior with --debuginfo flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--arch', 'all', '--debuginfo'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_called_once_with([
            'koji', 'download-build', '--debuginfo', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

    def test_multiple_builds(self, mocked_client_class, mocker):
        """
        Assert correct behavior with multiple builds.
        """
        mocked_client_class.send_request.return_value = EXAMPLE_QUERY_MUNCH_MULTI_BUILDS
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-pants-0.3.0-2.fc25,nodejs-grunt-wrap-0.3.0-2.fc25',
                '--arch', 'all'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        call.assert_any_call([
            'koji', 'download-build', 'nodejs-pants-0.3.0-2.fc25'])
        call.assert_any_call([
            'koji', 'download-build', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

    def test_empty_options(self, mocked_client_class):
        """Assert we return an error if either --updateid or --builds are not used."""
        runner = testing.CliRunner()

        result = runner.invoke(cli.download)

        assert result.output == 'ERROR: must specify at least one of --updateid or --builds\n'
        mocked_client_class.send_request.assert_not_called()

    def test_no_builds_warning(self, mocked_client_class, mocker):
        """
        Test the download() no builds found warning.
        """
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()
        no_builds_response = copy.copy(client_test_data.EXAMPLE_QUERY_MUNCH)
        no_builds_response.updates = []
        mocked_client_class.send_request.return_value = no_builds_response
        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-pants-0.3.0-2.fc25,nodejs-grunt-wrap-0.3.0-2.fc25'])

        assert result.exit_code == 0
        assert result.output == 'WARNING: No builds found!\n'
        call.assert_not_called()

    def test_some_builds_warning(self, mocked_client_class, mocker):
        """
        Test the download() some builds not found warning.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)

        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-pants-0.3.0-2.fc25,nodejs-grunt-wrap-0.3.0-2.fc25'])

        assert result.exit_code == 0
        assert result.output == ('WARNING: Some builds not found!\nDownloading packages '
                                 'from FEDORA-2017-c95b33872d\n')
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

    def test_failed_warning(self, mocked_client_class, mocker):
        """
        Test that we show a warning if a download fails.
        i.e. the subprocess call calling koji returns something.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value="Failure")
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

        assert result.exit_code == 0
        assert result.output == ('Downloading packages from FEDORA-2017-c95b33872d\n'
                                 'WARNING: download of nodejs-grunt-wrap-0.3.0-2.fc25 failed!\n')
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])

    def test_updateid(self, mocked_client_class, mocker):
        """
        Assert correct behavior with the --updateid flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.download,
            ['--updateid', 'FEDORA-2017-c95b33872d', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == 'Downloading packages from FEDORA-2017-c95b33872d\n'
        mocked_client_class.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'updateid': 'FEDORA-2017-c95b33872d'})
        call.assert_called_once_with([
            'koji', 'download-build', '--arch=noarch', '--arch={}'.format(platform.machine()),
            'nodejs-grunt-wrap-0.3.0-2.fc25'])


class TestComposeInfo:
    """
    This class tests the info_compose() function.
    """

    def test_successful_operation(self, mocked_client_class):
        """
        Assert that a successful compose info is handled properly.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_COMPOSE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(cli.info_compose, ['EPEL-7', 'stable'])

        assert result.exit_code == 0
        assert compare_output(result.output, client_test_data.EXPECTED_COMPOSE_OUTPUT)
        calls = [
            mock.call('composes/EPEL-7/stable', verb='GET')
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_compose_not_found(self, mocked_client_class):
        """
        Assert that info_compose() transforms a bodhi.client.bindings.ComposeNotFound into a
        click.BadParameter so that the user gets a nice error message.
        """
        server_error = HTTPError(
            response=build_response(
                404,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/request",
                "update not found",
            )
        )
        mocked_client_class.send_request.side_effect = server_error
        runner = testing.CliRunner()

        result = runner.invoke(cli.info_compose, ['EPEL-7', 'stable'])

        assert result.exit_code == 2
        if int(click.__version__.split('.')[0]) < 8:
            assert compare_output(
                result.output,
                ('Usage: info [OPTIONS] RELEASE REQUEST\n\n'
                    'Error: Invalid value for RELEASE/REQUEST: Compose with '
                    'request "stable" not found for release "EPEL-7"'))
        else:
            assert compare_output(
                result.output,
                ('Usage: info [OPTIONS] RELEASE REQUEST\n'
                    'Try \'info --help\' for help.\n\n'
                    'Error: Invalid value for RELEASE/REQUEST: Compose with '
                    'request "stable" not found for release "EPEL-7"'))
        mocked_client_class.send_request.assert_called_once_with(
            'composes/EPEL-7/stable', verb='GET'
        )

    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_COMPOSE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.info_compose,
            ['--url', 'http://localhost:6543', 'EPEL-7', 'stable']
        )

        assert result.exit_code == 0
        assert compare_output(result.output, client_test_data.EXPECTED_COMPOSE_OUTPUT)
        calls = [
            mock.call('composes/EPEL-7/stable', verb='GET'),
        ]
        assert mocked_client_class.send_request.mock_calls == calls


class TestListComposes:
    """Test the list_composes() function."""

    def test_single_compose(self, mocked_client_class, mocker):
        """Test without the -v flag."""
        mocker.patch.dict(
            client_test_data.EXAMPLE_COMPOSES_MUNCH,
            {'composes': [client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0]]}
        )
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_COMPOSES_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(cli.list_composes)

        assert result.exit_code == 0
        assert '*EPEL-7-stable  :   2 updates (requested)' in result.output
        assert ' EPEL-7-testing :   1 updates (requested)' not in result.output
        mocked_client_class.send_request.assert_called_once_with('composes/', verb='GET')

    def test_short(self, mocked_client_class):
        """Test without the -v flag."""
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_COMPOSES_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(cli.list_composes)

        assert result.exit_code == 0
        assert '*EPEL-7-stable  :   2 updates (requested)' in result.output
        assert ' EPEL-7-testing :   1 updates (requested)' in result.output
        mocked_client_class.send_request.assert_called_once_with('composes/', verb='GET')

    def test_verbose(self, mocked_client_class):
        """Test with the -v flag."""
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_COMPOSES_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(cli.list_composes, ['-v'])

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
        mocked_client_class.send_request.assert_called_once_with('composes/', verb='GET')


class TestNew:
    """
    Test the new() function.
    """

    def test_severity_flag(self, mocked_client_class, mocker):
        """Assert correct behavior with the --severity flag."""
        mocker.patch.dict(os.environ, {'BODHI_URL': 'http://example.com/tests/'})
        mocker.patch.dict(client_test_data.EXAMPLE_UPDATE_MUNCH, {'severity': 'urgent'})
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            [
                '--autokarma', '--autotime', 'bodhi-2.2.4-1.el7', '--severity', 'urgent',
                '--notes', 'No description.', '--stable-days', 7
            ]
        )

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('unspecified', 'urgent')
        assert compare_output(result.output, expected_output)
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_debug_flag(self, mocked_client_class, mocker):
        """Assert correct behavior with the --debug flag."""
        mocker.patch.dict(os.environ, {'BODHI_URL': 'http://example.com/tests/'})
        mocker.patch.dict(client_test_data.EXAMPLE_UPDATE_MUNCH, {'severity': 'urgent'})
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            [
                '--debug', '--autokarma', 'bodhi-2.2.4-1.el7', '--severity', 'urgent',
                '--notes', 'No description.'
            ]
        )

        assert result.exit_code == 0
        expected_output = 'No `errors` nor `decision` in the data returned\n' \
            + client_test_data.EXPECTED_UPDATE_OUTPUT.replace('unspecified', 'urgent')
        assert compare_output(result.output, expected_output)
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            [
                '--autokarma', 'bodhi-2.2.4-1.el7', '--url', 'http://localhost:6543',
                '--notes', 'No description.'
            ]
        )

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output)
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_file_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --file flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()
        with tempfile.NamedTemporaryFile() as update_file:
            update_file.write(UPDATE_FILE.encode('utf-8'))
            update_file.flush()

            result = runner.invoke(
                cli.new,
                [
                    '--autokarma', 'bodhi-2.2.4-1.el7', '--file', update_file.name,
                    '--url', 'http://example.com/tests'
                ]
            )

        assert result.exit_code == 0
        assert compare_output(result.output, client_test_data.EXPECTED_UPDATE_OUTPUT)
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_bodhi_client_exception(self, mocked_client_class):
        """
        Assert that a BodhiClientException gets returned to the user via click echo
        """
        exception_message = "This is a BodhiClientException message"
        mocked_client_class.send_request.side_effect = bindings.BodhiClientException(
            exception_message
        )
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            ['--autokarma', 'bodhi-2.2.4-1.el7', '--notes', 'No description.']
        )

        assert result.exit_code == 0
        assert "This is a BodhiClientException message" in result.output

    def test_exception(self, mocked_client_class):
        """
        Assert that any other Exception gets returned to the user as a traceback
        """
        exception_message = "This is an Exception message"
        mocked_client_class.send_request.side_effect = Exception(exception_message)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            ['--autokarma', 'bodhi-2.2.4-1.el7', '--notes', 'No description.']
        )

        assert result.exit_code == 0
        assert "Traceback (most recent call last):" in result.output
        assert "Exception: This is an Exception message" in result.output

    def test_close_bugs_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --close-bugs flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            [
                '--autokarma', 'bodhi-2.2.4-1.el7', '--bugs', '1234567', '--close-bugs',
                '--url', 'http://localhost:6543', '--notes', 'No description.'
            ]
        )

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output + '\n')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_display_name_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --display-name flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            [
                '--autokarma', 'bodhi-2.2.4-1.el7', '--bugs', '1234567', '--display-name',
                'fake display name', '--url', 'http://localhost:6543', '--notes', 'No description.'
            ]
        )

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output + '\n')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_from_tag_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --from-tag flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            [
                '--autokarma', 'fake_tag', '--bugs', '1234567', '--from-tag', '--url',
                'http://localhost:6543', '--notes', 'No description.'
            ]
        )

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output + '\n')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_from_tag_flag_multiple_tags(self, mocked_client_class):
        """
        Assert correct behavior with the --from-tag and multiple tags.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            [
                '--autokarma', 'fake tag', '--bugs', '1234567', '--from-tag', '--url',
                'http://localhost:6543', '--notes', 'No description.'
            ]
        )

        assert result.exit_code == 1
        assert result.output == 'ERROR: Can\'t specify more than one tag.\n'

    def test_new_update_without_notes(self, mocked_client_class):
        """
        Assert providing neither --notes-file nor --notes parameters to new update request
        results in an error.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            ['--autokarma', 'bodhi-2.2.4-1.el7', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 1
        assert result.output == ('ERROR: must specify at least one of --file,'
                                 ' --notes, or --notes-file\n')

    def test_security_update_with_unspecified_severity(self, mocked_client_class):
        """Assert not providing --severity to new security update request results in an error."""
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.new,
            ['bodhi-2.2.4-1.el7', '--notes', 'bla bla bla', '--type', 'security']
        )

        assert result.exit_code == 2
        if int(click.__version__.split('.')[0]) < 8:
            assert result.output == (
                'Usage: new [OPTIONS] BUILDS_OR_TAG\n\nError: Invalid '
                'value for severity: must specify severity for a security update\n')
        else:
            assert result.output == (
                'Usage: new [OPTIONS] BUILDS_OR_TAG\n'
                'Try \'new --help\' for help.\n\nError: Invalid '
                'value for severity: must specify severity for a security update\n')


class TestPrintOverrideKojiHint:
    """
    Test the _print_override_koji_hint() function.
    """
    def test_with_release_id(self, mocker, mocked_client_class):
        """Assert that the correct string is printed when the override Munch has a release_id."""
        echo = mocker.patch('bodhi.client.cli.click.echo')
        override = munch.Munch({
            'submitter': munch.Munch({'name': 'bowlofeggs'}),
            'build': munch.Munch({'nvr': 'python-pyramid-1.5.6-3.fc25', 'release_id': 15}),
            'expiration_date': '2017-02-24'})
        c = mocked_client_class()
        c.send_request.return_value = munch.Munch(
            {'releases': [munch.Munch({'dist_tag': 'f25'})]}
        )

        cli._print_override_koji_hint(override, c)

        echo.assert_called_once_with(
            '\n\nUse the following to ensure the override is active:\n\n\t$ koji '
            'wait-repo f25-build --build=python-pyramid-1.5.6-3.fc25\n')
        c.send_request.assert_called_once_with('releases/', verb='GET',
                                               params={'ids': [15]})

    def test_without_release_id(self, mocker, mocked_client_class):
        """Assert that nothing is printed when the override Munch does not have a release_id."""
        echo = mocker.patch('bodhi.client.cli.click.echo')
        override = munch.Munch({
            'submitter': {'name': 'bowlofeggs'}, 'build': {'nvr': 'python-pyramid-1.5.6-3.el7'},
            'expiration_date': '2017-02-24'})
        c = mocked_client_class()
        c.send_request.return_value = 'response'

        cli._print_override_koji_hint(override, c)

        assert echo.call_count == 0
        assert c.send_request.call_count == 0


class TestQuery:
    """
    Test the query() function.
    """

    def test_query_single_update(self, mocked_client_class):
        """
        Assert we display correctly when the query returns a single update.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_QUERY_OUTPUT + '\n'
        calls = [
            mock.call(
                'updates/', verb='GET',
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
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_query_multiple_update(self, mocked_client_class, mocker):
        """
        Assert we display correctly when the query returns a single update.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH_MULTI
        mocker.patch("bodhi.client.bindings._days_since", return_value=17)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXAMPLE_QUERY_OUTPUT_MULTI
        mocked_client_class.send_request.assert_called_once_with(
            'updates/', verb='GET',
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

    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query,
            ['--builds', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_QUERY_OUTPUT.replace('example.com/tests',
                                                                         'localhost:6543')
        assert result.output == expected_output + '\n'
        calls = [
            mock.call(
                'updates/', verb='GET',
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
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_query_mine_flag_username_unset(self, mocked_client_class, mocker):
        """Assert that we use get the username."""
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.oidc = mocker.Mock()
        mocked_client_class.oidc.username = "dudemcpants"

        runner = testing.CliRunner()
        res = runner.invoke(cli.query, ['--mine'])

        assert res.exit_code == 0
        calls = [
            mocker.call(
                'updates/', verb='GET',
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
            mocker.call(
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_rows_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --rows flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query,
            ['--rows', 10])

        assert result.exit_code == 0
        calls = [
            mock.call(
                'updates/', verb='GET',
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
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_page_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --page flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query,
            ['--page', 5])

        assert result.exit_code == 0
        calls = [
            mock.call(
                'updates/', verb='GET',
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
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls


class TestQueryBuildrootOverrides:
    """
    This class tests the query_buildroot_overrides() function.
    """

    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query_buildroot_overrides,
            ['--user', 'bowlofeggs', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_QUERY_OVERRIDES_OUTPUT
        mocked_client_class.send_request.assert_called_once_with(
            'overrides/', verb='GET',
            params={'user': 'bowlofeggs'})

    def test_queryoverrides_mine_flag_username_unset(self, mocked_client_class, mocker):
        """Assert that we use get the username."""
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.oidc = mocker.Mock()
        mocked_client_class.oidc.username = "dudemcpants"

        runner = testing.CliRunner()
        res = runner.invoke(cli.query_buildroot_overrides, ['--mine'])

        assert res.exit_code == 0
        calls = [
            mock.call(
                'overrides/', verb='GET', params={'user': 'dudemcpants'}
            ),
            mock.call(
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_single_override(self, mocked_client_class):
        """Assert that querying a single override provides more detailed output."""
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_QUERY_SINGLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        mocked_client_class.send_request.side_effect = _send_request

        result = runner.invoke(cli.query_buildroot_overrides,
                               ['--builds', 'bodhi-2.10.1-1.fc25'])

        assert result.exit_code == 0
        assert result.output == (client_test_data.EXPECTED_OVERRIDES_OUTPUT
                                 + "1 overrides found (1 shown)\n")
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'overrides/',
            verb='GET',
            params={'builds': 'bodhi-2.10.1-1.fc25'}
        )
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            "releases/",
            verb='GET',
            params={'ids': [15]}
        )

    def test_rows_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --rows flag.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query_buildroot_overrides,
            ['--rows', 10])

        assert result.exit_code == 0
        mocked_client_class.send_request.assert_called_once_with(
            'overrides/', verb='GET',
            params={'rows_per_page': 10})

    def test_page_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --page flag.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query_buildroot_overrides,
            ['--page', 5])

        assert result.exit_code == 0
        mocked_client_class.send_request.assert_called_once_with(
            'overrides/', verb='GET', params={'page': 5})


class TestRequest:
    """
    This class tests the request() function.
    """
    def test_successful_operation(self, mocked_client_class, mocker):
        """
        Assert that a successful updates request is handled properly.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocker.patch.dict(os.environ, {'BODHI_OPENID_PROVIDER': 'https://id.example.com/'})
        runner = testing.CliRunner()

        result = runner.invoke(cli.request, [
            'bodhi-2.2.4-1.el7', 'revoke', '--url', 'http://example.com/tests/'
        ])

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
        assert mocked_client_class.send_request.mock_calls == calls
        client = mocked_client_class.instances[-1]
        assert client.base_url == "http://example.com/tests/"
        mocked_client_class._build_oidc_client.assert_called_with(
            constants.CLIENT_ID, 'https://id.example.com/'
        )

    def test_update_not_found(self, mocked_client_class):
        """
        Assert that request() transforms a bodhi.client.bindings.UpdateNotFound into a
        click.BadParameter so that the user gets a nice error message.
        """
        server_error = HTTPError(
            response=build_response(
                404,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/request",
                "update not found",
            )
        )
        mocked_client_class.send_request.side_effect = server_error
        runner = testing.CliRunner()

        result = runner.invoke(cli.request, ['bodhi-2.2.4-99.el7', 'revoke'])

        assert result.exit_code == 2
        if int(click.__version__.split('.')[0]) < 8:
            assert compare_output(
                result.output,
                ('Usage: request [OPTIONS] UPDATE STATE\n'
                 '\nError: Invalid value for UPDATE: Update not found: bodhi-2.2.4-99.el7\n'))
        else:
            assert compare_output(
                result.output,
                ('Usage: request [OPTIONS] UPDATE STATE\n'
                 'Try \'request --help\' for help.\n'
                 '\nError: Invalid value for UPDATE: Update not found: bodhi-2.2.4-99.el7\n'))
        mocked_client_class.send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-99.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-99.el7'})

    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.request,
            ['bodhi-2.2.4-99.el7', 'revoke', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace('example.com/tests',
                                                                          'localhost:6543')
        assert compare_output(result.output, expected_output)
        calls = [
            mock.call(
                'updates/bodhi-2.2.4-99.el7/request', verb='POST', auth=True,
                data={
                    'csrf_token': 'a_csrf_token', 'request': 'revoke',
                    'update': 'bodhi-2.2.4-99.el7'
                }
            ),
            mock.call(
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls


class TestSaveBuildrootOverrides:
    """
    Test the save_buildroot_overrides() function.
    """

    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        mocked_client_class.send_request.side_effect = _send_request

        result = runner.invoke(
            cli.save_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25', '--url', 'http://localhost:6543/', '--no-wait']
        )

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_OVERRIDES_OUTPUT
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = mocked_client_class.send_request.mock_calls[0][2]['data']['expiration_date']
        assert (datetime.utcnow() - expire_time) < timedelta(seconds=5)
        # There should be two calls to send_request(). The first to save the override, and the
        # second to find out the release tags so the koji wait-repo hint can be printed.
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'overrides/',
            verb='POST',
            auth=True,
            data={'expiration_date': expire_time,
                  'notes': 'No explanation given...',
                  'nvr': 'js-tag-it-2.0-1.fc25',
                  'csrf_token': 'a_csrf_token'}
        )
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            'releases/',
            verb='GET',
            params={'ids': [15]}
        )

    def test_wait_default(self, mocked_client_class, mocker):
        """Assert that the --wait flag is the default."""
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        mocked_client_class.send_request.side_effect = _send_request

        result = runner.invoke(
            cli.save_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25']
        )

        assert result.exit_code == 0
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'.format(
                client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT))
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    def test_wait_flag(self, mocked_client_class, mocker):
        """
        Assert correct behavior with the --wait flag.
        """
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        mocked_client_class.send_request.side_effect = _send_request

        result = runner.invoke(
            cli.save_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25', '--wait']
        )

        assert result.exit_code == 0
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'.format(
                client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT))
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    def test_wait_flag_fail(self, mocked_client_class, mocker):
        """
        Assert correct behavior when the command execution due to --wait flag fails.
        """
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=42)
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        mocked_client_class.send_request.side_effect = _send_request

        result = runner.invoke(
            cli.save_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25', '--wait']
        )

        assert result.exit_code == 42
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'
            'WARNING: ensuring active override failed for js-tag-it-2.0-1.fc25\n')
        expected_output = expected_output.format(client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT)
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    def test_create_multiple_overrides(self, mocked_client_class):
        """
        Assert correct behavior when user creates multiple overrides.
        """
        runner = testing.CliRunner()

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            response = client_test_data.EXAMPLE_QUERY_OVERRIDES_MUNCH
            del response['total']
            return response

        mocked_client_class.send_request.side_effect = _send_request
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
            cli.save_buildroot_overrides,
            [overrides_nvrs_str, '--url', 'http://localhost:6543/', '--no-wait']
        )

        assert result.exit_code == 0
        assert result.output == expected_output
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = mocked_client_class.send_request.mock_calls[0][2]['data']['expiration_date']
        assert (datetime.utcnow() - expire_time) < timedelta(seconds=5)
        # There should be one calls to send_request().
        assert mocked_client_class.send_request.call_count == 1
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'overrides/',
            verb='POST',
            auth=True,
            data={'expiration_date': expire_time,
                  'notes': 'No explanation given...',
                  'nvr': overrides_nvrs_str,
                  'csrf_token': 'a_csrf_token'}
        )


class TestWarnIfUrlOrOpenidAndStagingSet:
    """
    This class tests the _warn_if_url_and_staging_set() function.
    """
    def test_staging_false(self, mocker):
        """
        Nothing should be printed when staging is False.
        """
        echo = mocker.patch('bodhi.client.cli.click.echo')
        ctx = mock.MagicMock()
        ctx.params = {'staging': False}
        param = mock.MagicMock()
        param.name = 'url'

        result = cli._warn_staging_overrides(
            ctx, param, 'http://localhost:6543')

        assert result == 'http://localhost:6543'
        assert echo.call_count == 0

    def test_staging_missing(self, mocker):
        """
        Nothing should be printed when staging is not present in the context.
        """
        echo = mocker.patch('bodhi.client.cli.click.echo')
        ctx = mock.MagicMock()
        ctx.params = {}
        param = mock.MagicMock()
        param.name = 'url'

        result = cli._warn_staging_overrides(
            ctx, param, 'http://localhost:6543')

        assert result == 'http://localhost:6543'
        assert echo.call_count == 0

    def test_staging_and_default_url(self, mocker):
        """
        Nothing should be printed when staging is True and the URL is the default.
        """
        echo = mocker.patch('bodhi.client.cli.click.echo')
        ctx = mock.MagicMock()
        ctx.params = {'staging': True}
        param = mock.MagicMock()
        param.name = 'url'

        result = cli._warn_staging_overrides(
            ctx, param, constants.BASE_URL)

        assert result == constants.BASE_URL
        assert echo.call_count == 0

    def test_staging_and_default_idp(self, mocker):
        """
        Nothing should be printed when staging is True and the id_provider is the default.
        """
        echo = mocker.patch('bodhi.client.cli.click.echo')
        ctx = mock.MagicMock()
        ctx.params = {'staging': True}
        param = mock.MagicMock()
        param.name = 'id_provider'

        result = cli._warn_staging_overrides(
            ctx, param, constants.IDP)

        assert result == constants.IDP
        assert echo.call_count == 0

    def test_staging_true(self, mocker):
        """
        A warning should be printed to stderr when staging is True and url/openid provided.
        """
        echo = mocker.patch('bodhi.client.cli.click.echo')
        # Check url param when staging is set
        ctx = mock.MagicMock()
        ctx.params = {'staging': True}
        param = mock.MagicMock()
        param.name = 'url'

        result = cli._warn_staging_overrides(
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

        result = cli._warn_staging_overrides(ctx, param, True)

        assert result
        echo.assert_called_once_with(
            '\nWarning: url and staging flags are both set. url will be ignored.\n', err=True)

        # Check staging param when openid_api is set
        echo.reset_mock()
        ctx = mock.MagicMock()
        ctx.params = {'id_provider': 'fake_openid'}
        param = mock.MagicMock()
        param.name = 'staging'

        result = cli._warn_staging_overrides(ctx, param, True)

        assert result
        echo.assert_called_once_with(
            '\nWarning: id_provider and staging flags are both set. id_provider will be ignored.\n',
            err=True
        )


class TestEdit:
    """
    This class tests the edit() function.
    """

    def test_bugs_flag(self, mocked_client_class, mocker):
        """Assert that the --bugs flag is handled properly."""
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--bugs', '1234,5678'])

        assert result.exit_code == 0
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET')]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_severity_flag(self, mocked_client_class, mocker):
        """Assert that the --severity flag is handled properly."""
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--severity', 'low',
                       '--notes', 'Updated package.'])

        assert result.exit_code == 0
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_url_flag(self, mocked_client_class, mocker):
        """
        Assert that a successful updates edit request is handled properly.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--notes', 'this is an edited note',
                       '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_notes_file(self, mocked_client_class, mocker):
        """
        Assert that a valid notes-file is properly handled in a successful updates
        edit request.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()
        with runner.isolated_filesystem():
            with open('notefile.txt', 'w') as f:
                f.write('This is a --notes-file note!')

            result = runner.invoke(
                cli.edit, ['FEDORA-2017-c95b33872d', '--notes-file', 'notefile.txt',
                           '--url', 'http://localhost:6543'])

            assert result.exit_code == 0
            mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')
            calls = [
                mock.call(
                    'updates/', auth=True, verb='POST',
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
                    'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                    verb='GET'
                )
            ]
            assert mocked_client_class.send_request.mock_calls == calls

    def test_addbuilds_removebuilds(self, mocked_client_class, mocker):
        """
        Assert that a addbuilds and removebuilds are properly handled in a successful updates
        edit request.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--notes', 'add and remove builds',
                       '--addbuilds', 'tar-1.29-4.fc25,nedit-5.7-1.fc25',
                       '--removebuilds', 'nodejs-grunt-wrap-0.3.0-2.fc25',
                       '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        mocked_client_class.query.assert_called_with(updateid=u'FEDORA-2017-c95b33872d')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                u'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_from_tag_flag(self, mocked_client_class, mocker):
        """
        Assert correct behavior with the --from-tag flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        data = client_test_data.EXAMPLE_QUERY_MUNCH.copy()
        data.updates[0]['from_tag'] = 'fake_tag'
        data.updates[0]['release']['composed_by_bodhi'] = False
        mocked_client_class.query = mocker.Mock(return_value=data)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--from-tag',
                       '--notes', 'Updated package.',
                       '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_from_tag_flag_no_tag(self, mocked_client_class, mocker):
        """
        Assert --from-tag bails out if the update wasn't created from a tag.
        """
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--from-tag',
                       '--notes', 'Updated package.',
                       '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ("ERROR: This update was not created from a tag."
                                 " Please remove --from_tag and try again.\n")
        mocked_client_class.query.assert_called_with(
            updateid='FEDORA-2017-c95b33872d')

    def test_from_tag_addbuilds(self, mocked_client_class, mocker):
        """
        Assert --from-tag can't be used with --addbuilds.
        """
        data = client_test_data.EXAMPLE_QUERY_MUNCH.copy()
        data.updates[0]['from_tag'] = 'fake_tag'
        mocked_client_class.query = mocker.Mock(return_value=data)

        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--from-tag',
                       '--addbuilds', 'tar-1.29-4.fc25,nedit-5.7-1.fc25',
                       '--notes', 'Updated package.',
                       '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ("ERROR: You have to use the web interface to update"
                                 " builds in a side-tag update.\n")
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')

    def test_from_tag_removebuilds(self, mocked_client_class, mocker):
        """
        Assert --from-tag can't be used with --removebuilds.
        """
        data = client_test_data.EXAMPLE_QUERY_MUNCH.copy()
        data.updates[0]['from_tag'] = 'fake_tag'
        mocked_client_class.query = mocker.Mock(return_value=data)

        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--from-tag',
                       '--removebuilds', 'nodejs-grunt-wrap-0.3.0-2.fc25',
                       '--notes', 'Updated package.',
                       '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ("ERROR: You have to use the web interface to update"
                                 " builds in a side-tag update.\n")
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')

    def test_from_tag_missing_flag(self, mocked_client_class, mocker):
        """
        Assert --from-tag is required when editing a side-tag update.
        """
        data = client_test_data.EXAMPLE_QUERY_MUNCH.copy()
        data.updates[0]['from_tag'] = 'fake_tag'
        mocked_client_class.query = mocker.Mock(return_value=data)

        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d',
                       '--addbuilds', 'tar-1.29-4.fc25,nedit-5.7-1.fc25',
                       '--notes', 'Updated package.',
                       '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == ("ERROR: This update was created from a side-tag."
                                 " Please add --from_tag and try again.\n")
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')

    def test_notes_and_notes_file(self, mocked_client_class):
        """
        Assert providing both --notes-file and --notes parameters to an otherwise successful
        updates edit request results in an error.
        """
        runner = testing.CliRunner()
        with runner.isolated_filesystem():
            with open('notefile.txt', 'w') as f:
                f.write('This is a --notes-file note!')

            result = runner.invoke(
                cli.edit, ['FEDORA-2017-cc8582d738', '--notes', 'this is a notey note',
                           '--notes-file', 'notefile.txt', '--url', 'http://localhost:6543'])

            assert result.exit_code == 1
            assert result.output == 'ERROR: Cannot specify --notes and --notes-file\n'

    def test_wrong_update_id_argument(self):
        """
        Assert that an error is given if the edit update argument given is not an update id.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['drupal7-i18n-1.17-1', '--notes', 'this is an edited note',
                       '--url', 'http://localhost:6543'])
        assert result.exit_code == 2
        # Click 7.0 capitalizes UPDATE, and < 7 does not.
        # Click <= 7.0 uses " while > 7 uses '
        click_ver = [int(n) for n in click.__version__.split('.')]
        if click_ver < [7, 0]:
            label = '"update"'
            extra_help = ''
        elif click_ver == [7, 0]:
            label = '"UPDATE"'
            extra_help = ''
        elif click_ver < [8, 0]:
            label = "'UPDATE'"
            extra_help = ''
        else:
            label = "'UPDATE'"
            extra_help = 'Try \'edit --help\' for help.\n'
        expected = f'Usage: edit [OPTIONS] UPDATE\n{extra_help}\n' \
                   f'Error: Invalid value for {label}: ' \
                   f'Please provide an Update ID\n'

        assert result.output == expected

    def test_required_tasks(self, mocked_client_class, mocker):
        """
        Assert that valid required Taskotron Tasks are properly handled in a successful updates
        edit request.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)

        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d', '--notes', 'testing required tasks',
                       '--requirements', 'dist.depcheck dist.rpmdeplint', '--url',
                       'http://localhost:6543'])

        assert result.exit_code == 0
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_bodhi_client_exception(self, mocked_client_class):
        """
        Assert that a BodhiClientException gets returned to the user via click echo
        """
        exception_message = "This is a BodhiClientException message"
        mocked_client_class.send_request.side_effect = \
            bindings.BodhiClientException(exception_message)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-cc8582d738', '--notes', 'No description.'])

        assert result.exit_code == 0
        assert "This is a BodhiClientException message" in result.output

    def test_edit_bugless_update_without_bugs_param(self, mocked_client_class, mocker):
        """Test editing an update with no bugs, without passing '--bugs' to it."""
        mocker.patch.dict(client_test_data.EXAMPLE_QUERY_MUNCH['updates'][0], {'bugs': []})
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-c95b33872d'])

        assert result.exit_code == 0
        mocked_client_class.query.assert_called_with(updateid='FEDORA-2017-c95b33872d')
        calls = [
            mock.call(
                'updates/', auth=True, verb='POST',
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
                'updates/FEDORA-EPEL-2016-3081a94111/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_edit_security_update_with_unspecified_severity(self, mocked_client_class, mocker):
        """Assert 'unspecified' severity while editing a security update results in an error."""
        mocked_client_class.query = mocker.Mock(return_value=client_test_data.EXAMPLE_QUERY_MUNCH)
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit, ['FEDORA-2017-cc8582d738', '--notes', 'this is an edited note',
                       '--type', 'security', '--severity', 'unspecified'])

        assert result.exit_code == 2
        if int(click.__version__.split('.')[0]) < 8:
            assert result.output == ('Usage: edit [OPTIONS] UPDATE\n\nError: Invalid '
                                     'value for severity: must specify severity for '
                                     'a security update\n')
        else:
            assert result.output == ('Usage: edit [OPTIONS] UPDATE\n'
                                     'Try \'edit --help\' for help.\n\nError: Invalid '
                                     'value for severity: must specify severity for '
                                     'a security update\n')


class TestEditBuildrootOverrides:
    """
    Test the edit_buildroot_overrides() function.
    """

    def test_expired_override(self, mocked_client_class):
        """
        Assert that a successful overrides edit request expires the request
        when --expired flag is set.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_EXPIRED_OVERRIDE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_buildroot_overrides,
            [
                'js-tag-it-2.0-1.fc25', '--url', 'http://localhost:6543/',
                '--notes', 'This is an expired override', '--expire'
            ]
        )

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_EXPIRED_OVERRIDES_OUTPUT
        # datetime is a C extension that can't be mocked, so let's just assert that the time is
        # about a week away.
        expire_time = mocked_client_class.send_request.mock_calls[0][2]['data']['expiration_date']
        assert (datetime.utcnow() - expire_time) < timedelta(seconds=5)
        mocked_client_class.send_request.assert_called_once_with(
            'overrides/', verb='POST', auth=True,
            data={
                'expiration_date': expire_time, 'notes': 'This is an expired override',
                'nvr': 'js-tag-it-2.0-1.fc25', 'edited': 'js-tag-it-2.0-1.fc25',
                'csrf_token': 'a_csrf_token', 'expired': True})

    def test_wait_flag(self, mocked_client_class, mocker):
        """
        Assert correct behavior with the --wait flag.
        """
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=0)
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        mocked_client_class.send_request.side_effect = _send_request

        result = runner.invoke(
            cli.edit_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25', '--wait'])

        assert result.exit_code == 0
        expected_output = (
            '{}\n\nRunning koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25\n\n'.format(
                client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT))
        assert result.output == expected_output
        call.assert_called_once_with(
            ('koji', 'wait-repo', 'f25-build', '--build=js-tag-it-2.0-1.fc25'),
            stderr=-1, stdout=-1)

    def test_wait_flag_fail(self, mocked_client_class, mocker):
        """
        Assert correct behavior when the command execution due to --wait flag fails.
        """
        call = mocker.patch('bodhi.client.cli.subprocess.call', return_value=24)
        runner = testing.CliRunner()
        responses = [client_test_data.EXAMPLE_OVERRIDE_MUNCH,
                     client_test_data.EXAMPLE_GET_RELEASE_15]

        def _send_request(*args, **kwargs):
            """Mock the response from send_request()."""
            return responses.pop(0)

        mocked_client_class.send_request.side_effect = _send_request

        result = runner.invoke(
            cli.edit_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25', '--wait'])

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
    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.create_release,
            ['--name', 'F27', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        mocked_client_class.send_request.assert_called_once_with(
            'releases/', verb='POST', auth=True,
            data={'dist_tag': None, 'csrf_token': 'a_csrf_token', 'staging': False,
                  'eol': None, 'name': 'F27',
                  'testing_tag': None, 'pending_stable_tag': None, 'long_name': None, 'state': None,
                  'version': None, 'override_tag': None, 'branch': None, 'id_prefix': None,
                  'pending_testing_tag': None, 'pending_signing_tag': None, 'stable_tag': None,
                  'candidate_tag': None, 'mail_template': None, 'composed_by_bodhi': True,
                  'create_automatic_updates': False, 'package_manager': None,
                  'testing_repository': None})

    def test_create_with_errors(self, mocked_client_class):
        """
        Assert errors are printed if returned back in the request
        """
        mocked_client_class.send_request.return_value = {
            "errors": [{"description": "an error was encountered... :("}]
        }
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.create_release,
            ['--name', 'F27', '--url', 'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == "ERROR: an error was encountered... :(\n"


class TestEditRelease:
    """
    Test the edit_release() function.
    """
    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release,
            ['--name', 'F27', '--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'releases/F27',
            verb='GET',
            auth=True
        )
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            'releases/', verb='POST', auth=True,
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
                  'testing_repository': None, 'eol': None})

    def test_new_name_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --new-name flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release,
            ['--name', 'F27', '--new-name', 'fedora27', '--url',
             'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'releases/F27',
            verb='GET',
            auth=True)
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            'releases/', verb='POST', auth=True,
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
                  'testing_repository': None, 'eol': None})

    def test_edit_no_name_provided(self, mocked_client_class):
        """
        Assert we print an error and no request is sent if a --name is not provided.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release,
            ['--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543'])

        assert result.output == "ERROR: Please specify the name of the release to edit\n"
        mocked_client_class.send_request.assert_not_called()

    def test_edit_with_errors(self, mocked_client_class):
        """
        Assert errors are printed if returned back in the request
        """
        mocked_client_class.send_request.return_value = {
            "errors": [{"description": "an error was encountered... :("}]
        }
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release,
            ['--name', 'F27', '--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543'])

        assert result.exit_code == 1
        assert result.output == "ERROR: an error was encountered... :(\n"

    def test_edit_mail_template(self, mocked_client_class):
        """
        Assert correct behavior while editing 'mail_template' name.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release,
            ['--name', 'F27', '--mail-template', 'edited_fedora_errata_template'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'releases/F27',
            verb='GET',
            auth=True
        )
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            'releases/', verb='POST', auth=True,
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
                  'testing_repository': None, 'eol': None})

    def test_edit_not_composed_by_bodhi_flag(self, mocked_client_class):
        """
        Assert correct behavior while editing 'composed_by_bodhi' flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release,
            ['--name', 'F27', '--not-composed-by-bodhi'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'releases/F27',
            verb='GET',
            auth=True)
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            'releases/', verb='POST', auth=True,
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
                  'testing_repository': None, 'eol': None, 'create_automatic_updates': False})

    def test_edit_create_automatic_updates_flag(self, mocked_client_class):
        """
        Assert correct behavior while editing 'created_automatic_updates' flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release,
            ['--name', 'F27', '--create-automatic-updates'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            'releases/F27',
            verb='GET',
            auth=True
        )
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            'releases/', verb='POST', auth=True,
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
                  'package_manager': 'unspecified', 'testing_repository': None, 'eol': None})

    def test_edit_eol(self, mocked_client_class):
        """
        Assert correct behavior while editing the end-of-life date.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.edit_release, ["--name", "F27", "--eol", "2021-06-14"]
        )

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT
        assert mocked_client_class.send_request.call_count == 2
        assert mocked_client_class.send_request.mock_calls[0] == mock.call(
            "releases/F27", verb="GET", auth=True
        )
        assert mocked_client_class.send_request.mock_calls[1] == mock.call(
            "releases/",
            verb="POST",
            auth=True,
            data={
                "dist_tag": "f27",
                "testing_tag": "f27-updates-testing",
                "branch": "f27",
                "pending_stable_tag": "f27-updates-pending",
                "pending_signing_tag": "f27-signing-pending",
                "long_name": "Fedora 27",
                "state": "pending",
                "version": "27",
                "name": "F27",
                "override_tag": "f27-override",
                "id_prefix": "FEDORA",
                "composed_by_bodhi": True,
                "pending_testing_tag": "f27-updates-testing-pending",
                "stable_tag": "f27-updates",
                "candidate_tag": "f27-updates-candidate",
                "mail_template": "fedora_errata_template",
                "create_automatic_updates": False,
                "package_manager": "unspecified",
                "testing_repository": None,
                "eol": date(2021, 6, 14),
                "edited": "F27",
                "csrf_token": "a_csrf_token",
                "staging": False,
            },
        )


class TestInfo:
    """
    Test the info() function.
    """
    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_RELEASE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(cli.info_release, ['--url', 'http://localhost:6543', 'F27'])

        assert result.exit_code == 0
        assert result.output == client_test_data.EXPECTED_RELEASE_OUTPUT.replace('Saved r', 'R')
        mocked_client_class.send_request.assert_called_once_with(
            'releases/F27', verb='GET', auth=False)

    def test_info_with_errors(self, mocked_client_class):
        """
        Assert errors are printed if returned back in the request
        """
        mocked_client_class.send_request.return_value = {
            "errors": [{"description": "an error was encountered... :("}]
        }

        runner = testing.CliRunner()

        result = runner.invoke(cli.info_release, ['--url', 'http://localhost:6543', 'F27'])

        assert result.exit_code == 1
        assert result.output == "ERROR: an error was encountered... :(\n"


class TestListReleases:
    """
    Test the list_releases() function.
    """
    def test_url_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --url flag.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_RELEASE_MUNCH_NO_ARCHIVED
        runner = testing.CliRunner()

        result = runner.invoke(cli.list_releases, ['--url', 'http://localhost:6543'])

        expected_output = '{}\n{}\n{}'.format(
            client_test_data.EXPECTED_PENDING_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_CURRENT_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_FROZEN_RELEASES_LIST_OUTPUT,
        )

        assert result.exit_code == 0
        assert result.output == expected_output
        mocked_client_class.send_request.assert_called_once_with(
            'releases/', params={
                'rows_per_page': None, 'page': None, 'exclude_archived': True
            }, verb='GET'
        )

    def test_pagination(self, mocked_client_class):
        """
        Assert correct behavior using pagination.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_RELEASE_MUNCH_NO_ARCHIVED
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.list_releases, ['--url', 'http://localhost:6543', '--rows', 4, '--page', 1]
        )

        expected_output = '{}\n{}\n{}'.format(
            client_test_data.EXPECTED_PENDING_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_CURRENT_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_FROZEN_RELEASES_LIST_OUTPUT,
        )

        assert result.exit_code == 0
        assert result.output == expected_output
        mocked_client_class.send_request.assert_called_once_with(
            'releases/', params={
                'rows_per_page': 4, 'page': 1, 'exclude_archived': True
            }, verb='GET'
        )

    def test_display_archived_flag(self, mocked_client_class):
        """
        Assert correct behavior with the --display-archived flag.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_RELEASE_MUNCH_WITH_ARCHIVED
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.list_releases, ['--url', 'http://localhost:6543', '--display-archived']
        )

        expected_output = '{}\n{}\n{}'.format(
            client_test_data.EXPECTED_PENDING_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_ARCHIVED_RELEASES_LIST_OUTPUT,
            client_test_data.EXPECTED_CURRENT_RELEASES_LIST_OUTPUT,
        )

        assert result.exit_code == 0
        assert result.output == expected_output
        mocked_client_class.send_request.assert_called_once_with(
            'releases/', params={
                'rows_per_page': None, 'page': None, 'exclude_archived': False
            }, verb='GET'
        )

    def test_list_releases_with_errors(self, mocked_client_class):
        """
        Assert errors are printed if returned back in the request
        """
        mocked_client_class.send_request.return_value = {
            "errors": [{"description": "an error was encountered... :("}]
        }
        runner = testing.CliRunner()

        result = runner.invoke(cli.list_releases, ['--url', 'http://localhost:6543'])

        assert result.exit_code == 2
        assert result.output == "an error was encountered... :(\n"
        mocked_client_class.send_request.assert_called_once_with(
            'releases/', params={
                'rows_per_page': None, 'page': None, 'exclude_archived': True
            }, verb='GET'
        )


class TestPrintReleasesList:
    """
    Test the print_releases_list() function
    """
    def test_only_pending_state(self, mocker):
        """Assert that only release with pending state is printed ."""
        echo = mocker.patch('bodhi.client.cli.click.echo')
        releases = [{"state": "pending", "name": "test_name"}]

        cli.print_releases_list(releases)

        assert echo.call_count == 2
        assert echo.mock_calls[0][1][0] == 'pending:'
        assert echo.mock_calls[1][1][0] == '  Name:                test_name'

    def test_only_archived_state(self, mocker):
        """Assert that only release with archived state is printed ."""
        echo = mocker.patch('bodhi.client.cli.click.echo')
        releases = [{"state": "archived", "name": "test_name"}]

        cli.print_releases_list(releases)

        assert echo.call_count == 2
        assert echo.mock_calls[0][1][0] == '\narchived:'
        assert echo.mock_calls[1][1][0] == '  Name:                test_name'

    def test_only_current_state(self, mocker):
        """Assert that only release with current state is printed ."""
        echo = mocker.patch('bodhi.client.cli.click.echo')
        releases = [{"state": "current", "name": "test_name"}]

        cli.print_releases_list(releases)

        assert echo.call_count == 2
        assert echo.mock_calls[0][1][0] == '\ncurrent:'
        assert echo.mock_calls[1][1][0] == '  Name:                test_name'


class TestHandleErrors:
    """
    Test the handle_errors decorator
    """

    def test_bodhi_client_exception(self, mocked_client_class):
        """
        Assert that BodhiClientExceptions are presented as expected
        """
        mocked_client_class.send_request.side_effect = \
            bindings.BodhiClientException("Pants Exception")
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.save_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25'])

        assert result.exit_code == 2
        assert result.output == "Pants Exception\n"


class TestPrintResp:
    """
    Test the print_resp() method.
    """

    def test_single_update(self, mocked_client_class):
        """
        Test the single update response returns the update.
        """
        mocked_client_class.send_request.return_value = client_test_data.SINGLE_UPDATE_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query,
            ['--url', 'http://localhost:6543'])

        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
            'example.com/tests', 'localhost:6543'
        )
        assert compare_output(result.output, expected_output)

    def test_total_missing_in_response(self, mocked_client_class):
        """If total is missing in the response, the x updates found (y shown) should not appear."""
        response = copy.deepcopy(client_test_data.EXAMPLE_QUERY_MUNCH)
        del response['total']
        mocked_client_class.send_request.return_value = response
        runner = testing.CliRunner()

        result = runner.invoke(cli.query, ['--url', 'http://example.com/tests'])

        assert 'updates found' not in result.output

    def test_unhandled_response(self, mocked_client_class):
        """
        Test that if a response is not identified by print_resp, then we just print the response
        """
        mocked_client_class.send_request.return_value = client_test_data.UNMATCHED_RESP
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.query,
            [])

        assert result.output == "{'pants': 'pants'}\n"

    def test_caveats_output(self, mocked_client_class):
        """
        Assert we correctly output caveats.
        """
        mocked_client_class.send_request.return_value = \
            client_test_data.EXAMPLE_OVERRIDE_MUNCH_CAVEATS
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.save_buildroot_overrides,
            ['js-tag-it-2.0-1.fc25'])

        assert "\nCaveats:\nthis is a caveat\n" in result.output


class TestWaive:
    """
    Test the waive() function.
    """

    def test_waive_show_and_tests(self, mocked_client_class):
        """
        Assert we error if the user specifies --show and --test.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.waive,
            [
                '--show', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543',
                '--test', 'foobar'
            ]
        )

        assert result.exit_code == 1
        assert result.output == (
            'ERROR: You can not list the unsatisfied requirements and waive them at '
            'the same time, please use either --show or --test=... but not both.\n')

    def test_waive_show_invalid_data_returned(self, mocked_client_class):
        """
        Assert we error correctly when the data returned by bodhi does not fit our expectations.
        """
        mocked_client_class.send_request.return_value = client_test_data.EXAMPLE_QUERY_MUNCH
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.waive,
            ['--show', 'nodejs-grunt-wrap-0.3.0-2.fc25', '--url', 'http://localhost:6543'])

        assert result.exit_code == 0
        assert result.output == 'Could not retrieve the unsatisfied requirements from bodhi.\n'

        mocked_client_class.send_request.assert_called_once_with(
            'updates/nodejs-grunt-wrap-0.3.0-2.fc25/get-test-results',
            verb='GET'
        )

    def test_waive_show_with_errors(self, mocked_client_class):
        """
        Assert we display the proper error messages when we try to list the unsatisfied
        requirements and there are errors in the data returned.
        """
        mocked_client_class.send_request.return_value = munch.Munch({
            'errors': [
                munch.Munch({'description': 'Could not contact greenwave, error code was 500'}),
            ]
        })

        runner = testing.CliRunner()

        result = runner.invoke(
            cli.waive,
            ['--show', 'FEDORA-2017-cc8582d738', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert result.output == (
            'One or more errors occurred while retrieving the unsatisfied requirements:\n'
            '  - Could not contact greenwave, error code was 500\n')

    def test_waive_show_successful_missing_req(self, mocked_client_class):
        """
        Assert we display the unsatisfied requirements when everything is fine.
        """
        mocked_client_class.send_request.return_value = munch.Munch({
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
            cli.waive,
            ['--show', 'FEDORA-2017-cc8582d738', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert result.output == (
            'CI status: Two missing tests\nMissing tests:\n'
            '  - dist.rpmdeplint\n'
            '  - fedora-atomic-ci\n')

    def test_waive_show_successful_no_missing_req(self, mocked_client_class):
        """
        Assert we display the unsatisfied requirements when everything is fine but there
        are no unsatisfied requirements.
        """
        mocked_client_class.send_request.return_value = munch.Munch({
            'decision': munch.Munch({
                'summary': 'No tests required',
                'unsatisfied_requirements': []
            }),

        })

        runner = testing.CliRunner()

        result = runner.invoke(
            cli.waive,
            ['--show', 'FEDORA-2017-cc8582d738', '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert result.output == (
            'CI status: No tests required\n'
            'Missing tests: None\n')

    def test_waive_missing_comment(self, mocked_client_class):
        """
        Assert we error if the user is trying to waive some tests without specifying a comment.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.waive,
            ['--test', 'dist.rpmdeplint', 'FEDORA-2017-cc8582d738',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 1
        assert result.output == ('ERROR: A comment is mandatory when waiving '
                                 'unsatisfied requirements\n')

    def test_waive_all(self, mocked_client_class):
        """
        Assert we properly waive all missing requirements when asked.
        """
        mocked_client_class.send_request.side_effect = [
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
            cli.waive,
            ['--test', 'all', 'FEDORA-2017-c95b33872d', 'Expected errors',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert 'Waiving all unsatisfied requirements\n' in result.output
        assert 'CI Status: All tests passed\n' in result.output

        calls = [
            mock.call(
                'updates/FEDORA-2017-c95b33872d/waive-test-results',
                auth=True,
                data={'comment': 'Expected errors', 'csrf_token': 'a_csrf_token',
                      'tests': None, 'update': 'FEDORA-2017-c95b33872d'},
                verb='POST',
            ),
            mock.call(
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls

    def test_waive_some(self, mocked_client_class):
        """
        Assert we properly waive some missing requirements.
        """
        mocked_client_class.send_request.side_effect = [
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
            cli.waive,
            ['--test', 'dist.rpmdeplint', '--test', 'fedora-atomic-ci',
             'FEDORA-2017-c95b33872d', 'Expected errors',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert ('Waiving unsatisfied requirements: dist.rpmdeplint, fedora-atomic-ci\n'
                in result.output)
        assert 'CI Status: All tests passed\n' in result.output

        calls = [
            mock.call(
                'updates/FEDORA-2017-c95b33872d/waive-test-results',
                auth=True,
                data={'comment': 'Expected errors', 'csrf_token': 'a_csrf_token',
                      'tests': ('dist.rpmdeplint', 'fedora-atomic-ci'),
                      'update': 'FEDORA-2017-c95b33872d'},
                verb='POST',
            ),
            mock.call(
                'updates/FEDORA-2017-c95b33872d/get-test-results',
                verb='GET'
            )
        ]
        assert mocked_client_class.send_request.mock_calls == calls


class TestTriggerTests:
    """
    Test the trigger_tests() function.
    """

    def test_trigger_success(self, mocked_client_class):
        """
        Assert we properly trigger tests for updated.
        """
        mocked_client_class.send_request.return_value = munch.Munch({
            'decision': munch.Munch({
                'summary': 'Tests triggered',
            }),

        })
        runner = testing.CliRunner()

        result = runner.invoke(
            cli.trigger_tests,
            ['FEDORA-2017-c95b33872d',
             '--url', 'http://localhost:6543']
        )

        assert result.exit_code == 0
        assert "Tests triggered" in result.output

        mocked_client_class.send_request.assert_called_once_with(
            'updates/FEDORA-2017-c95b33872d/trigger-tests',
            auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'FEDORA-2017-c95b33872d'},
            verb='POST')
