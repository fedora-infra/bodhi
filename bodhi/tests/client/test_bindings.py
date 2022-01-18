# Copyright 2008-2019 Red Hat, Inc. and others.
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
"""This module contains tests for bodhi.client.bindings."""
from datetime import datetime, timedelta
from unittest import mock
import copy

import fedora.client
import munch
import pytest

from bodhi.client import bindings
from bodhi.tests import client as client_test_data
from bodhi.tests.utils import compare_output


@mock.patch('fedora.client.openidproxyclient.FEDORA_OPENID_API', 'default')
class TestBodhiClient___init__:
    """
    This class contains tests for the BodhiClient.__init__() method.
    """
    def test_base_url_not_ends_in_slash(self):
        """
        If the base_url doesn't end in a slash, __init__() should append one.
        """
        client = bindings.BodhiClient(base_url='http://localhost:6543')

        assert client.base_url == 'http://localhost:6543/'
        assert fedora.client.openidproxyclient.FEDORA_OPENID_API == 'default'

    def test_openid_api(self):
        """Test the openid_api parameter."""
        client = bindings.BodhiClient(
            base_url='http://example.com/bodhi/', username='some_user', password='s3kr3t',
            staging=False, timeout=60, openid_api='https://example.com/api/v1/')

        assert client.base_url == 'http://example.com/bodhi/'
        assert client.login_url == 'http://example.com/bodhi/login'
        assert client.username == 'some_user'
        assert client.timeout == 60
        assert client._password == 's3kr3t'
        assert client.csrf_token == ''
        assert fedora.client.openidproxyclient.FEDORA_OPENID_API == 'https://example.com/api/v1/'

    def test_staging_false(self):
        """
        Test with staging set to False.
        """
        client = bindings.BodhiClient(base_url='http://example.com/bodhi/', username='some_user',
                                      password='s3kr3t', staging=False, timeout=60)

        assert client.base_url == 'http://example.com/bodhi/'
        assert client.login_url == 'http://example.com/bodhi/login'
        assert client.username == 'some_user'
        assert client.timeout == 60
        assert client._password == 's3kr3t'
        assert client.csrf_token == ''
        assert fedora.client.openidproxyclient.FEDORA_OPENID_API == 'default'

    def test_staging_true(self):
        """
        Test with staging set to True.
        """
        client = bindings.BodhiClient(
            base_url='http://example.com/bodhi/', username='some_user', password='s3kr3t',
            staging=True, retries=5, openid_api='ignored')

        assert client.base_url == bindings.STG_BASE_URL
        assert client.login_url == bindings.STG_BASE_URL + 'login'
        assert client.username == 'some_user'
        assert client.timeout is None
        assert client.retries == 5
        assert client._password == 's3kr3t'
        assert client.csrf_token == ''
        assert fedora.client.openidproxyclient.FEDORA_OPENID_API == bindings.STG_OPENID_API


class TestBodhiClient_comment:
    """
    Test the BodhiClient.comment() method.
    """
    def test_comment(self):
        """
        Test the comment() method.
        """
        client = bindings.BodhiClient()
        client.csrf_token = 'a token'
        client.send_request = mock.MagicMock(return_value='response')

        response = client.comment('bodhi-2.4.0-1.fc25', 'It ate my cat!', karma=-1)

        assert response == 'response'
        client.send_request.assert_called_once_with(
            'comments/', verb='POST', auth=True,
            data={'update': 'bodhi-2.4.0-1.fc25', 'text': 'It ate my cat!', 'karma': -1,
                  'csrf_token': 'a token'})


class TestBodhiClient_compose_str:
    """Test the BodhiClient.compose_str() method."""

    def test_error_message(self):
        """Assert that an error message gets rendered in the long form."""
        with mock.patch.dict(client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0],
                             {'error_message': 'some error'}):
            s = bindings.BodhiClient.compose_str(
                client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0], minimal=False)

        assert '*EPEL-7-stable  :   2 updates (requested)' in s
        assert 'Content Type: rpm' in s
        assert 'Started: 2018-03-15 17:25:22' in s
        assert 'Updated: 2018-03-15 17:25:22' in s
        assert 'Updates:' in s
        assert 'FEDORA-EPEL-2018-50566f0a39: uwsgi-2.0.16-1.el7' in s
        assert 'FEDORA-EPEL-2018-328e2b8c27: qtpass-1.2.1-3.el7' in s
        assert 'Error: some error' in s

    def test_minimal_false(self):
        """Test with minimal False."""
        s = bindings.BodhiClient.compose_str(
            client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0], minimal=False)

        assert '*EPEL-7-stable  :   2 updates (requested)' in s
        assert 'Content Type: rpm' in s
        assert 'Started: 2018-03-15 17:25:22' in s
        assert 'Updated: 2018-03-15 17:25:22' in s
        assert 'Updates:' in s
        assert 'FEDORA-EPEL-2018-50566f0a39: uwsgi-2.0.16-1.el7' in s
        assert 'FEDORA-EPEL-2018-328e2b8c27: qtpass-1.2.1-3.el7' in s
        assert 'Error' not in s

    def test_minimal_true(self):
        """Test with minimal True."""
        s = bindings.BodhiClient.compose_str(
            client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0], minimal=True)

        assert s == '*EPEL-7-stable  :   2 updates (requested) '

    def test_non_security_update(self):
        """Non-security updates should not have a leading *."""
        with mock.patch.dict(client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0],
                             {'security': False}):
            s = bindings.BodhiClient.compose_str(
                client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0], minimal=True)

        assert s == ' EPEL-7-stable  :   2 updates (requested) '


class TestBodhiClient_init_username:
    """Test the BodhiClient.init_username() method."""
    TEST_EMPTY_OBJECT_SESSION_CACHE = '{}'
    TEST_FAILED_SESSION_CACHE = '{"https://bodhi.fedoraproject.org/:bowlofeggs": []}'
    TEST_HOT_SESSION_CACHE = '{"https://bodhi.fedoraproject.org/:bowlofeggs": [["stuff", "login"]]}'
    TEST_OTHER_SESSION_CACHE = '{"https://other_domain/:bowlofeggs": [["stuff", "login"]]}'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_auth_cache_empty(self, exists, _load_cookies, mock_input, mock_open):
        """
        Test the method when there is no username, the session cache exists, and the session cache
        is 0 bytes.
        """
        exists.return_value = True
        mock_open.side_effect = mock.mock_open(read_data='')
        mock_input.return_value = 'pongou'
        client = bindings.BodhiClient()

        client.init_username()

        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 1
        mock_open.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert client.username == 'pongou'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_auth_cache_empty_object(self, exists, _load_cookies, mock_input, mock_open):
        """
        Test the method when there is no username, the session cache exists, and the session cache
        is an empty object.
        """
        exists.return_value = True
        mock_open.side_effect = mock.mock_open(read_data=self.TEST_EMPTY_OBJECT_SESSION_CACHE)
        mock_input.return_value = 'pongou'
        client = bindings.BodhiClient()

        client.init_username()

        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 1
        mock_open.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert client.username == 'pongou'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_auth_cache_failed(self, exists, _load_cookies, mock_input, mock_open):
        """
        Test the method when there is no username, the session cache exists, and the session cache
        is missing the cookies.
        """
        exists.return_value = True
        mock_open.side_effect = mock.mock_open(read_data=self.TEST_FAILED_SESSION_CACHE)
        mock_input.return_value = 'pongou'
        client = bindings.BodhiClient()

        client.init_username()

        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 1
        mock_open.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert client.username == 'pongou'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_auth_cache_hot(self, exists, _load_cookies, mock_input, mock_open):
        """
        Test the method when there is no username, the session cache exists, and the session cache
        has cookies.
        """
        exists.return_value = True
        mock_open.side_effect = mock.mock_open(read_data=self.TEST_HOT_SESSION_CACHE)
        client = bindings.BodhiClient()

        client.init_username()

        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 0
        mock_open.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert client.username == 'bowlofeggs'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.json.loads')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_auth_cache_loop(self, exists, loads, _load_cookies, mock_input, mock_open):
        """
        Test the method when there is no username, the session cache exists, and the session cache
        has cookies but iteration is needed to find them.
        """
        def fake_keys():
            return [
                'http://wrong_host:wrong', 'also:wrong',
                'https://bodhi.fedoraproject.org/:correct',
                'https://bodhi.fedoraproject.org/:shouldntgethere']

        exists.return_value = True
        loads.return_value.keys.side_effect = fake_keys
        mock_open.side_effect = mock.mock_open(read_data=self.TEST_HOT_SESSION_CACHE)
        client = bindings.BodhiClient()

        client.init_username()

        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        loads.assert_called_once_with(self.TEST_HOT_SESSION_CACHE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 0
        mock_open.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert client.username == 'correct'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_auth_cache_missing(self, exists, _load_cookies, mock_input, mock_open):
        """
        Test the method when there is no username and the session cache doesn't exist.
        """
        exists.return_value = False
        mock_input.return_value = 'pongou'
        client = bindings.BodhiClient()

        client.init_username()

        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 1
        assert mock_open.call_count == 0
        assert client.username == 'pongou'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_auth_cache_other_domain(self, exists, _load_cookies, mock_input, mock_open):
        """
        Test the method when there is no username, the session cache exists, and the session cache
        has cookies but they are for a different domain.
        """
        exists.return_value = True
        mock_open.side_effect = mock.mock_open(read_data=self.TEST_OTHER_SESSION_CACHE)
        mock_input.return_value = 'pongou'
        client = bindings.BodhiClient()

        client.init_username()

        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 1
        mock_open.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert client.username == 'pongou'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_username_set(self, exists, _load_cookies, mock_input, mock_open):
        """
        Test the method when the username is set.
        """
        client = bindings.BodhiClient(username='coolbeans')

        client.init_username()

        assert exists.call_count == 0
        assert _load_cookies.mock_calls == [mock.call()]
        assert mock_input.call_count == 0
        assert mock_open.call_count == 0
        assert client.username == 'coolbeans'


class TestBodhiClient_csrf:
    """
    Test the BodhiClient.csrf() method.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.init_username')
    def test_with_csrf_token(self, init_username):
        """
        Test the method when csrf_token is set.
        """
        client = bindings.BodhiClient()
        client.csrf_token = 'a token'
        client.send_request = mock.MagicMock(return_value='response')

        csrf = client.csrf()

        assert csrf == 'a token'
        assert client.send_request.call_count == 0
        # No need to init the username since we already have a token.
        assert init_username.call_count == 0

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_without_csrf_token_with_cookies(self, exists, _load_cookies, mock_input,
                                             mock_open):
        """
        Test the method when csrf_token is not set and has_cookies() returns True.
        """
        exists.return_value = True
        mock_open.side_effect = mock.mock_open(
            read_data=TestBodhiClient_init_username.TEST_HOT_SESSION_CACHE)
        client = bindings.BodhiClient()
        client.has_cookies = mock.MagicMock(return_value=True)
        client.login = mock.MagicMock(return_value='login successful')
        client.send_request = mock.MagicMock(return_value={'csrf_token': 'a great token'})

        csrf = client.csrf()

        assert csrf == 'a great token'
        assert client.csrf_token == 'a great token'
        client.has_cookies.assert_called_once_with()
        assert client.login.call_count == 0
        client.send_request.assert_called_once_with('csrf', verb='GET', auth=True)
        # Ensure that init_username() was called and did its thing.
        exists.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert _load_cookies.mock_calls == [mock.call(), mock.call()]
        assert mock_input.call_count == 0
        mock_open.assert_called_once_with(fedora.client.openidbaseclient.b_SESSION_FILE)
        assert client.username == 'bowlofeggs'

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.input', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_without_csrf_token_without_cookies(self, exists, _load_cookies, mock_input,
                                                mock_open):
        """
        Test the method when csrf_token is not set and has_cookies() returns False.
        """
        client = bindings.BodhiClient(username='pongou', password='illnevertell')
        client.has_cookies = mock.MagicMock(return_value=False)
        client.login = mock.MagicMock(return_value='login successful')
        client.send_request = mock.MagicMock(return_value={'csrf_token': 'a great token'})

        csrf = client.csrf()

        assert csrf == 'a great token'
        assert client.csrf_token == 'a great token'
        client.has_cookies.assert_called_once_with()
        client.login.assert_called_once_with('pongou', 'illnevertell')
        client.send_request.assert_called_once_with('csrf', verb='GET', auth=True)
        # Ensure that init_username() didn't do anything since a username was given.
        assert exists.call_count == 0
        assert _load_cookies.mock_calls == [mock.call()]
        assert mock_input.call_count == 0
        assert mock_open.call_count == 0
        assert client.username == 'pongou'


class TestBodhiClient_latest_builds:
    """
    Test the BodhiClient.latest_builds() method.
    """
    def test_latest_builds(self):
        """
        Test latest_builds().
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='bodhi-2.4.0-1.fc25')

        latest_builds = client.latest_builds('bodhi')

        assert latest_builds == 'bodhi-2.4.0-1.fc25'
        client.send_request.assert_called_once_with('latest_builds', params={'package': 'bodhi'})


class TestBodhiClient_get_compose:
    """
    This class contains tests for BodhiClient.get_compose().
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/composes/EPEL-7/stable', status=404,
                    msg='update not found'))
    def test_404_error(self, send_request, __init__):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient(staging=False)

        with pytest.raises(bindings.ComposeNotFound) as exc:
            client.get_compose('EPEL-7', 'stable')

        assert exc.value.release == 'EPEL-7'
        assert exc.value.request == 'stable'

        send_request.assert_called_once_with('composes/EPEL-7/stable', verb='GET')
        __init__.assert_called_once_with(staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_COMPOSE_MUNCH)
    def test_successful_request(self, send_request, __init__):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient(staging=False)

        response = client.get_compose('EPEL-7', 'stable')

        assert response == client_test_data.EXAMPLE_COMPOSE_MUNCH
        send_request.assert_called_once_with('composes/EPEL-7/stable', verb='GET')
        __init__.assert_called_once_with(staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_other_ServerError(self, send_request, __init__):
        """
        Test for the case when a non-404 ServerError is raised.
        """
        server_error = fedora.client.ServerError(
            url='http://example.com/tests/composes/EPEL-7/stable', status=500,
            msg='Internal server error')
        send_request.side_effect = server_error
        client = bindings.BodhiClient(staging=False)

        with pytest.raises(fedora.client.ServerError) as exc:
            client.get_compose('EPEL-7', 'stable')

        assert exc.value is server_error

        send_request.assert_called_once_with('composes/EPEL-7/stable', verb='GET')
        __init__.assert_called_once_with(staging=False)


class TestBodhiClient_list_composes:
    """Test the BodhiClient.list_composes() method."""

    def test_list_composes(self):
        """Assert a correct call to send_request() from list_composes()."""
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='some_composes')

        composes = client.list_composes()

        assert composes == 'some_composes'
        client.send_request.assert_called_once_with('composes/', verb='GET')


class TestBodhiClient_list_overrides:
    """
    Test the BodhiClient.list_overrides() method.
    """
    def test_with_user(self):
        """
        Test with the user parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(user='bowlofeggs')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'user': 'bowlofeggs'})

    def test_without_parameters(self):
        """
        Test without the parameters.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides()

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET', params={})

    def test_with_package(self):
        """
        Test with the package parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(packages='bodhi')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'packages': 'bodhi'})

    def test_with_expired(self):
        """
        Test --expired with the expired/active click boolean parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(expired=True)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'expired': True})

    def test_with_active(self):
        """
        Test --active with the expired/active click boolean parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(expired=False)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'expired': False})

    def test_with_releases(self):
        """
        Test with the releases parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(releases='F24')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'releases': 'F24'})

    def test_with_builds(self):
        """
        Test with the builds parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(builds='python-1.5.6-3.fc26')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'builds': 'python-1.5.6-3.fc26'})

    def test_with_rows_per_page(self):
        """
        Test with the rows_per_page parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(rows_per_page=10)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'rows_per_page': 10})

    def test_with_page(self):
        """
        Test with the page parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='response')

        response = client.list_overrides(page=5)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'page': 5})


class TestBodhiClient_override_str:
    """
    Test the BodhiClient.override_str() method.
    """
    def test_with_min_dict(self):
        """
        Test override_str() with a dict argument and minimal set to true.
        """
        override = {
            'submitter': {'name': 'bowlofeggs'}, 'build': {'nvr': 'python-pyramid-1.5.6-3.el7'},
            'expiration_date': '2017-02-24'}

        override = bindings.BodhiClient.override_str(override)

        assert override == "bowlofeggs's python-pyramid-1.5.6-3.el7 override (expires 2017-02-24)"

    def test_with_dict(self):
        """
        Test override_str() with a dict argument.
        """
        override = {
            'submitter': {'name': 'bowlofeggs'}, 'build': {'nvr': 'js-tag-it-2.0-1.fc25'},
            'expiration_date': '2017-03-07 23:05:31', 'notes': 'No explanation given...',
            'expired_date': None}

        override = bindings.BodhiClient.override_str(override, minimal=False)

        assert override == client_test_data.EXPECTED_OVERRIDE_STR_OUTPUT.rstrip()

    def test_with_str(self):
        """
        Test override_str() with a str argument.
        """
        override = bindings.BodhiClient.override_str('this is an override')

        assert override == 'this is an override'


class TestBodhiClient_password:
    """
    This class contains tests for the BodhiClient.password property.
    """
    @mock.patch('bodhi.client.bindings.getpass.getpass', return_value='typed password')
    def test_password_not_set(self, getpass):
        """
        Assert correct behavior when the _password attribute is not set.
        """
        client = bindings.BodhiClient()

        assert client.password == 'typed password'

        getpass.assert_called_once_with()

    @mock.patch('bodhi.client.bindings.getpass.getpass', return_value='typed password')
    def test_password_set(self, getpass):
        """
        Assert correct behavior when the _password attribute is set.
        """
        client = bindings.BodhiClient(password='arg password')

        assert client.password == 'arg password'
        assert getpass.call_count == 0


class TestBodhiClient_query:
    """
    Test BodhiClient.query().
    """
    def test_with_bugs_empty_string(self):
        """
        Test with the bugs kwargs set to an empty string.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(builds='bodhi-2.4.0-1.fc26', bugs='')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26', 'bugs': None})

    def test_with_limit(self):
        """
        Assert that the limit kwargs gets translated to rows_per_page correctly.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(builds='bodhi-2.4.0-1.fc26', limit=50)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26', 'rows_per_page': 50})

    def test_with_mine_false(self):
        """
        Assert correct behavior when the mine kwargs is False.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(builds='bodhi-2.4.0-1.fc26', mine=False)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26', 'mine': False})

    def test_with_mine_true(self):
        """
        Assert correct behavior when the mine kwargs is True.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')
        client.username = 'bowlofeggs'

        result = client.query(builds='bodhi-2.4.0-1.fc26', mine=True)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET',
            params={'builds': 'bodhi-2.4.0-1.fc26', 'mine': True, 'user': 'bowlofeggs'})

    def test_with_package_el_build(self):
        """
        Test with the package arg expressed as an el7 build.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(package='bodhi-2.4.0-1.el7')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.el7'})

    def test_with_package_epel_id(self):
        """
        Test with the package arg expressed as a EPEL update id.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(package='FEDORA-EPEL-2017-c3b112eb9e')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'updateid': 'FEDORA-EPEL-2017-c3b112eb9e'})

    def test_with_package_fc_build(self):
        """
        Test with the package arg expressed as a fc26 build.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(package='bodhi-2.4.0-1.fc26')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26'})

    def test_with_package_fedora_id(self):
        """
        Test with the package arg expressed as a Fedora update id.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(package='FEDORA-2017-52506b30d4')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'updateid': 'FEDORA-2017-52506b30d4'})

    def test_with_package_name(self):
        """
        Test with the package arg expressed as a package name.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(package='bodhi')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi'})

    def test_with_release_list(self):
        """
        Test with a 'release' kwarg set to a list.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', release=['f27'])

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'releases': ['f27']})

    def test_with_release_str(self):
        """
        Test with a 'release' kwarg set to a str.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', release='f26')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'releases': ['f26']})

    def test_with_type_(self):
        """
        Test with the type_ kwarg.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', type_='security')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'type': 'security'})

    def test_with_rows_per_page(self):
        """
        Test with the 'rows_per_page' kwarg.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', rows_per_page=10)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'rows_per_page': 10})

    def test_with_page(self):
        """
        Test with the 'page' kwarg.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', page=5)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'page': 5})


class TestBodhiClient_save:
    """
    This class contains tests for BodhiClient.save().
    """
    def test_with_type_(self):
        """
        Assert that save() handles type_ as a kwargs for backwards compatibility.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        kwargs = {
            'builds': ['bodhi-2.4.0-1.fc26'], 'type_': 'enhancement', 'notes': 'This is a test',
            'request': 'testing', 'autokarma': True, 'stable_karma': 3, 'unstable_karma': -3,
            'severity': 'low'}

        response = client.save(**kwargs)

        assert response == 'return_value'
        kwargs['type'] = kwargs['type_']
        kwargs['csrf_token'] = 'a token'
        client.send_request.assert_called_once_with('updates/', verb='POST', auth=True, data=kwargs)

    def test_without_type_(self):
        """
        Assert correct operation when type_ isn't given.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        kwargs = {
            'builds': ['bodhi-2.4.0-1.fc26'], 'type': 'enhancement', 'notes': 'This is a test',
            'request': 'testing', 'autokarma': True, 'stable_karma': 3, 'unstable_karma': -3,
            'severity': 'low'}

        response = client.save(**kwargs)

        assert response == 'return_value'
        kwargs['csrf_token'] = 'a token'
        client.send_request.assert_called_once_with('updates/', verb='POST', auth=True, data=kwargs)


class TestBodhiClient_save_override:
    """
    This class contains tests for BodhiClient.save_override().
    """
    def test_save_override(self):
        """
        Test the save_override() method.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        now = datetime.utcnow()
        response = client.save_override(nvr='python-pyramid-1.5.6-3.el7',
                                        duration=2,
                                        notes='This is needed to build bodhi-2.4.0.')

        assert response == 'return_value'
        actual_expiration = client.send_request.mock_calls[0][2]['data']['expiration_date']
        client.send_request.assert_called_once_with(
            'overrides/', verb='POST', auth=True,
            data={'nvr': 'python-pyramid-1.5.6-3.el7',
                  'expiration_date': actual_expiration,
                  'csrf_token': 'a token', 'notes': 'This is needed to build bodhi-2.4.0.'})
        # Since we can't mock utcnow() since it's a C extension, let's just make sure the expiration
        # date sent is within 5 minutes of the now variable. It would be surprising if it took more
        # than 5 minutes to start the function and execute its first instruction!
        expected_expiration = now + timedelta(days=2)
        assert (actual_expiration - expected_expiration) < timedelta(minutes=5)

    def test_save_override_edit(self):
        """
        Test the save_override() method with the edit argument.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        now = datetime.utcnow()
        response = client.save_override(nvr='python-pyramid-1.5.6-3.el7',
                                        duration=2,
                                        notes='This is needed to build bodhi-2.4.0.',
                                        edit=True)

        assert response == 'return_value'
        actual_expiration = client.send_request.mock_calls[0][2]['data']['expiration_date']
        client.send_request.assert_called_once_with(
            'overrides/', verb='POST', auth=True,
            data={'nvr': 'python-pyramid-1.5.6-3.el7',
                  'expiration_date': actual_expiration,
                  'csrf_token': 'a token', 'notes': 'This is needed to build bodhi-2.4.0.',
                  'edited': 'python-pyramid-1.5.6-3.el7'})
        # Since we can't mock utcnow() since it's a C extension, let's just make sure the expiration
        # date sent is within 5 minutes of the now variable. It would be surprising if it took more
        # than 5 minutes to start the function and execute its first instruction!
        expected_expiration = now + timedelta(days=2)
        assert (actual_expiration - expected_expiration) < timedelta(minutes=5)

    def test_save_override_expired(self):
        """
        Test the save_override() method with the edit argument.
        """
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        now = datetime.utcnow()
        response = client.save_override(nvr='python-pyramid-1.5.6-3.el7',
                                        duration=2,
                                        notes='This is needed to build bodhi-2.4.0.',
                                        expired=True)

        assert response == 'return_value'
        actual_expiration = client.send_request.mock_calls[0][2]['data']['expiration_date']
        client.send_request.assert_called_once_with(
            'overrides/', verb='POST', auth=True,
            data={'nvr': 'python-pyramid-1.5.6-3.el7',
                  'expiration_date': actual_expiration,
                  'csrf_token': 'a token', 'notes': 'This is needed to build bodhi-2.4.0.',
                  'expired': True})
        # Since we can't mock utcnow() since it's a C extension, let's just make sure the expiration
        # date sent is within 5 minutes of the now variable. It would be surprising if it took more
        # than 5 minutes to start the function and execute its first instruction!
        expected_expiration = now + timedelta(days=2)
        assert (actual_expiration - expected_expiration) < timedelta(minutes=5)


class TestBodhiClient_request:
    """
    This class contains tests for BodhiClient.request().
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/request', status=404,
                    msg='update not found'))
    def test_404_error(self, send_request, __init__):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with pytest.raises(bindings.UpdateNotFound) as exc:
            client.request('bodhi-2.2.4-1.el7', 'revoke')

        assert exc.value.update == 'bodhi-2.2.4-1.el7'

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH)
    def test_successful_request(self, send_request, __init__):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        response = client.request('bodhi-2.2.4-1.el7', 'revoke')

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_other_ServerError(self, send_request, __init__):
        """
        Test for the case when a non-404 ServerError is raised.
        """
        server_error = fedora.client.ServerError(
            url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/request', status=500,
            msg='Internal server error')
        send_request.side_effect = server_error
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with pytest.raises(fedora.client.ServerError) as exc:
            client.request('bodhi-2.2.4-1.el7', 'revoke')

        assert exc.value is server_error

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)


class TestBodhiClient_update_str:
    """This test contains tests for BodhiClient.update_str."""
    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH,
        {'bugs': [{'bug_id': 1234, 'title': 'it broke'}, {'bug_id': 1235, 'title': 'halp'}]})
    def test_bugs(self):
        """Ensure correct output when there are bugs on the update."""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(
            text,
            client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
                'Autotime: True', 'Autotime: True\n   Bugs: 1234 - it broke\n    : 1235 - halp'))

    @mock.patch('bodhi.client.bindings.datetime.datetime')
    def test_minimal(self, mock_datetime):
        """Ensure correct output when minimal is True."""
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH,
        {'date_pushed': '',
         'pushed': False,
         'status': 'pending'})
    @mock.patch('bodhi.client.bindings.datetime.datetime')
    def test_minimal_not_pushed(self, mock_datetime):
        """Ensure correct output when minimal is True and not yet pushed."""
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 5, 23, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        rpm        pending   '
                           '2016-10-05 (0)')
        assert text == expected_output

    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH,
        {'type': 'security'})
    @mock.patch('bodhi.client.bindings.datetime.datetime')
    def test_minimal_type_security(self, mock_datetime):
        """Ensure correct output when minimal is True and type security"""
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = ('*bodhi-2.2.4-1.el7                        rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH,
        {'builds': [{'epoch': 0, 'nvr': 'bodhi-2.2.4-1.el7', 'signed': True},
                    {'epoch': 0, 'nvr': 'bodhi-pants-2.2.4-1.el7', 'signed': True}]})
    @mock.patch('bodhi.client.bindings.datetime.datetime')
    def test_minimal_with_multiple_builds(self, mock_datetime):
        """Ensure correct output when minimal is True, and multiple builds"""
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        rpm        stable    '
                           '2016-10-21 (2)\n  bodhi-pants-2.2.4-1.el7')
        assert text == expected_output

    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH,
        {'builds': [], 'title': 'update-title'})
    @mock.patch('bodhi.client.bindings.datetime.datetime')
    def test_minimal_no_builds(self, mock_datetime):
        """Ensure correct output when minimal is True, and there are no builds"""
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' update-title                             rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    @mock.patch.dict(client_test_data.EXAMPLE_UPDATE_MUNCH, {'title': None, 'builds': []})
    @mock.patch('bodhi.client.bindings.datetime.datetime')
    def test_minimal_no_title(self, mock_datetime):
        """Ensure correct output when minimal is True, and there are neither a title nor builds"""
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' FEDORA-EPEL-2016-3081a94111              '
                           'rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    @mock.patch.dict(client_test_data.EXAMPLE_UPDATE_MUNCH, {'content_type': None})
    @mock.patch('bodhi.client.bindings.datetime.datetime')
    def test_minimal_no_content_type(self, mock_datetime):
        """Ensure correct output when minimal is True, and and there is no content-type"""
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        '
                           'unspecified  stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    @mock.patch.dict(client_test_data.EXAMPLE_UPDATE_MUNCH, {'request': 'stable'})
    def test_request_stable(self):
        """Ensure correct output when the update is request stable."""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)
        print("This is", text)

        assert compare_output(
            text,
            client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
                'Autotime: True', 'Autotime: True\n     Request: stable'))

    def test_severity(self):
        """Test that severity is rendered."""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'Severity: unspecified' in text

    def test_with_autokarma_set(self):
        """
        Ensure correct operation when autokarma is True..
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t')
        client.base_url = 'http://example.com/tests/'

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(text, client_test_data.EXPECTED_UPDATE_OUTPUT)

    def test_with_autokarma_unset(self):
        """
        Ensure correct operation when autokarma is False.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t')
        client.base_url = 'http://example.com/tests/'
        update = copy.deepcopy(client_test_data.EXAMPLE_UPDATE_MUNCH)
        # Set the update's autokarma and to False.
        update.autokarma = False

        text = client.update_str(update)

        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
            'Autokarma: True  [-3, 3]', 'Autokarma: False  [-3, 3]')
        assert compare_output(text, expected_output)

    def test_autotime_set(self):
        """
        Ensure correct operation when autotime is True.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t')
        client.base_url = 'http://example.com/tests/'

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(text, client_test_data.EXPECTED_UPDATE_OUTPUT)

    def test_autotime_unset(self):
        """
        Ensure correct operation when autotime is False.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t')
        client.base_url = 'http://example.com/tests/'
        update = copy.deepcopy(client_test_data.EXAMPLE_UPDATE_MUNCH)
        # Set the update's autotime and to False.
        update.autotime = False

        text = client.update_str(update)

        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
            'Autotime: True', 'Autotime: False')
        assert compare_output(text, expected_output)

    def test_update_as_string(self):
        """Ensure we return a string if update is a string"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'

        text = client.update_str("this is a string")

        assert text == "this is a string"

    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH.comments[0],
        {'text': 'This comment contains a unicode char ☺. '})
    def test_update_with_unicode_comment(self):
        """Ensure unicode content in update comments is correctly handled"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(
            text,
            client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
                'Comments: This update has been submitted for testing by bowlofeggs. ',
                'Comments: This comment contains a unicode char ☺. '))

    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH,
        {'notes': 'This note contains a unicode char ☺'})
    def test_update_with_unicode_note(self):
        """Ensure unicode content in update notes is correctly handled"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'Notes: This note contains a unicode char ☺' in text

    @mock.patch('bodhi.client.bindings.BodhiClient.get_test_status')
    def test_ci_status_errors(self, get_test_status):
        """Ensure that ci error is displayed"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status.return_value = munch.Munch(
            {'errors': [munch.Munch({'description': 'bar'})]})

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'CI Status: bar\n' in text

    @mock.patch('bodhi.client.bindings.BodhiClient.get_test_status')
    def test_ci_status(self, get_test_status):
        """Ensure that ci information is displayed"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status.return_value = munch.Munch(
            {'decision': munch.Munch({'summary': 'no tests required', 'waivers': []})}
        )

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'CI Status: no tests required\n' in text

    @mock.patch('bodhi.client.bindings.BodhiClient.get_test_status')
    def test_waived_tests(self, get_test_status):
        """Ensure that information about waived tests is rendered"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status.return_value = munch.Munch(
            {'decision': munch.Munch({
                'summary': 'no tests required',
                'waivers': [{'comment': 'This is fine. See BZ#1566485', 'id': 150,
                             'product_version': 'fedora-28', 'proxied_by': None,
                             'subject': {'item': 'slop-7.4-1.fc28', 'type': 'koji_build'},
                             'subject_identifier': 'slop-7.4-1.fc28', 'subject_type': 'koji_build',
                             'testcase': 'dist.rpmlint', 'timestamp': '2018-06-29T00:20:20.425844',
                             'username': 'netvor', 'waived': True}]})}
        )

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert(
            '     Waivers: netvor - 2018-06-29 00:20:20\n'
            '              This is fine. See BZ#1566485\n'
            '              build: slop-7.4-1.fc28\n'
            '              testcase: dist.rpmlint\n'
            in text
        )

    @mock.patch('bodhi.client.bindings.BodhiClient.get_test_status')
    def test_ci_status_new_format(self, get_test_status):
        """Ensure that ci information is displayed with Greenwave's new format"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status.return_value = munch.Munch(
            {'decisions': [munch.Munch({'summary': 'no tests required', 'waivers': []})]}
        )

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'CI Status: no tests required\n' in text

    @mock.patch.dict(
        client_test_data.EXAMPLE_UPDATE_MUNCH,
        {'notes': 'This note contains:\n* multiline formatting\n* bullet points\n\n'})
    def test_notes_multiline(self):
        """Ensure that multiline notes are rendered"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'Notes: This note contains:\n' in text
        assert '     : * multiline formatting\n' in text
        assert '     : * bullet points\n' in text


class TestErrorhandled:
    """
    This class tests the errorhandled decorator.
    """
    def test_failure_with_given_errors(self):
        """
        Test the failure case for when errors were given in the response.
        """
        @bindings.errorhandled
        def im_gonna_fail_but_ill_be_cool_about_it(x, y, z=None):
            assert x == 1
            assert y == 2
            assert z == 3

            return {'errors': [{'description': 'insert'}, {'description': 'coin(s)'}]}

        with pytest.raises(bindings.BodhiClientException) as exc:
            im_gonna_fail_but_ill_be_cool_about_it(1, y=2, z=3)

        assert str(exc.value) == 'insert\ncoin(s)'

    def test_retry_on_auth_failure_failure(self):
        """
        Test the decorator when the wrapped method raises an AuthError the second time it is run.

        This test ensures that the decorator will give up after one retry if the wrapped method
        raises a fedora.client.AuthError, raising the AuthError in question.

        This test was written to assert the fix for
        https://github.com/fedora-infra/bodhi/issues/1474
        """
        a_fake_self = mock.MagicMock()
        a_fake_self.csrf_token = 'some_token'
        a_fake_self.call_count = 0

        @bindings.errorhandled
        def wrong_password_lol(a_fake_self):
            a_fake_self.call_count = a_fake_self.call_count + 1
            raise fedora.client.AuthError('wrong password lol')

        with pytest.raises(fedora.client.AuthError) as exc:
            # Wrong password always fails, so the second call should allow the Exception to be
            # raised.
            wrong_password_lol(a_fake_self)

        assert str(exc.value) == 'wrong password lol'
        a_fake_self._session.cookies.clear.assert_called_once_with()
        assert a_fake_self.csrf_token is None
        assert a_fake_self.call_count == 2

    def test_retry_on_auth_failure_success(self):
        """
        Test the decorator when the wrapped method raises an AuthError the first time it is run.

        This test ensures that the decorator will retry the wrapped method if it raises a
        fedora.client.AuthError, after clearing cookies and the csrf token.

        This test was written to assert the fix for
        https://github.com/fedora-infra/bodhi/issues/1474
        """
        a_fake_self = mock.MagicMock()
        a_fake_self.csrf_token = 'some_token'
        a_fake_self.call_count = 0

        @bindings.errorhandled
        def wrong_password_lol(a_fake_self):
            a_fake_self.call_count = a_fake_self.call_count + 1

            # Fail on the first call with an AuthError to simulate bad session cookies.
            if a_fake_self.call_count == 1:
                raise fedora.client.AuthError('wrong password lol')

            return 'here you go'

        # No Exception should be raised.
        wrong_password_lol(a_fake_self)

        a_fake_self._session.cookies.clear.assert_called_once_with()
        assert a_fake_self.csrf_token is None
        assert a_fake_self.call_count == 2

    def test_retry_on_captcha_key_failure(self):
        """
        Test the decorator when the wrapped method returns a captch_key error.

        This test ensures that the decorator will retry the wrapped method if it returns a
        captcha_key error, after clearing cookies and the csrf token.

        This test was written to assert the fix for
        https://github.com/fedora-infra/bodhi/issues/1787
        """
        a_fake_self = mock.MagicMock()
        a_fake_self.csrf_token = 'some_token'
        a_fake_self.call_count = 0

        @bindings.errorhandled
        def captcha_plz(a_fake_self):
            a_fake_self.call_count = a_fake_self.call_count + 1

            # Fail on the first call with a captcha_key error to simulate unauth'd user on a
            # comment.
            if a_fake_self.call_count == 1:
                return {'errors': [{'name': 'captcha_key'}]}

            return 'here you go'

        # No Exception should be raised.
        captcha_plz(a_fake_self)

        a_fake_self._session.cookies.clear.assert_called_once_with()
        assert a_fake_self.csrf_token is None
        assert a_fake_self.call_count == 2

    def test_success(self):
        """
        Test the decorator for the success case.
        """
        @bindings.errorhandled
        def im_gonna_be_cool(x, y, z=None):
            assert x == 1
            assert y == 2
            assert z == 3

            return 'here you go'

        assert im_gonna_be_cool(1, 2, 3) == 'here you go'

    def test_unexpected_error(self):
        """
        Test the failure case when errors are not given in the response.
        """
        @bindings.errorhandled
        def im_gonna_fail_and_i_wont_be_cool_about_it(x, y, z=None):
            assert x == 1
            assert y == 2
            assert z == 3

            return {'errors': ['MEAN ERROR']}

        with pytest.raises(bindings.BodhiClientException) as exc:
            im_gonna_fail_and_i_wont_be_cool_about_it(1, 2, z=3)

        assert str(exc.value) == 'An unhandled error occurred in the BodhiClient'


class TestUpdateNotFound:
    """
    This class tests the UpdateNotFound class.
    """
    def test___init__(self):
        """
        Assert that __init__() works properly.
        """
        exc = bindings.UpdateNotFound('bodhi-2.2.4-1.el7')

        assert exc.update == 'bodhi-2.2.4-1.el7'
        assert type(exc.update) == str

    def test___str__(self):
        """
        Assert that __str__() works properly.
        """
        exc = bindings.UpdateNotFound('bodhi-2.2.4-1.el7')

        assert str(exc.update) == 'bodhi-2.2.4-1.el7'
        assert type(str(exc.update)) == str
        assert str(exc) == 'Update not found: bodhi-2.2.4-1.el7'


class TestBodhiClient_candidates:
    """
    Test the BodhiClient.candidates() method.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies', mock.MagicMock())
    @mock.patch('bodhi.client.bindings.BodhiClient.get_koji_session')
    @mock.patch('bodhi.client.bindings.log.exception')
    def test_failure(self, exception, get_koji_session):
        """Ensure correct handling when talking to Koji raises an Exception."""
        get_koji_session.return_value.listTagged.side_effect = [
            [{'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc25', 'nvr': 'bodhi-2.9.0-1.fc25',
              'owner_name': 'bowlofeggs'},
             {'name': 'ipsilon', 'version': '2.0.2', 'release': '1.fc25',
              'nvr': 'ipsilon-2.0.2-1.fc25', 'owner_name': 'puiterwijk'}],
            IOError("Bet you didn't expect this.")]
        client = bindings.BodhiClient(username='bowlofeggs')
        client.send_request = mock.MagicMock(
            return_value={'releases': [{'candidate_tag': 'f25-updates-testing'},
                                       {'candidate_tag': 'f26-updates-testing'}]})

        results = client.candidates()

        assert results == [{'release': '1.fc25',
                            'version': '2.9.0',
                            'name': 'bodhi',
                            'owner_name': 'bowlofeggs',
                            'nvr': 'bodhi-2.9.0-1.fc25'}]
        get_koji_session.assert_called_once_with()
        assert (
            get_koji_session.return_value.listTagged.mock_calls
            == [mock.call('f25-updates-testing', latest=True),
                mock.call('f26-updates-testing', latest=True)])
        client.send_request.assert_called_once_with('releases/', params={}, verb='GET')
        exception.assert_called_once_with(
            "Unable to query candidate builds for %s", {'candidate_tag': 'f26-updates-testing'})

    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies', mock.MagicMock())
    @mock.patch('bodhi.client.bindings.BodhiClient.get_koji_session')
    def test_success(self, get_koji_session):
        """Ensure correct behavior when there are no errors talking to Koji."""
        get_koji_session.return_value.listTagged.side_effect = [
            [{'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc25', 'nvr': 'bodhi-2.9.0-1.fc25',
              'owner_name': 'bowlofeggs'},
             {'name': 'ipsilon', 'version': '2.0.2', 'release': '1.fc25',
              'nvr': 'ipsilon-2.0.2-1.fc25', 'owner_name': 'puiterwijk'}],
            [{'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc26', 'nvr': 'bodhi-2.9.0-1.fc26',
              'owner_name': 'bowlofeggs'}]]
        client = bindings.BodhiClient(username='bowlofeggs')
        client.send_request = mock.MagicMock(
            return_value={'releases': [{'candidate_tag': 'f25-updates-testing'},
                                       {'candidate_tag': 'f26-updates-testing'}]})

        results = client.candidates()

        assert results == [{'release': '1.fc25',
                            'version': '2.9.0',
                            'name': 'bodhi',
                            'owner_name': 'bowlofeggs',
                            'nvr': 'bodhi-2.9.0-1.fc25'},
                           {'release': '1.fc26',
                            'version': '2.9.0',
                            'name': 'bodhi',
                            'owner_name': 'bowlofeggs',
                            'nvr': 'bodhi-2.9.0-1.fc26'}
                           ]
        get_koji_session.assert_called_once_with()
        assert (
            get_koji_session.return_value.listTagged.mock_calls
            == [mock.call('f25-updates-testing', latest=True),
                mock.call('f26-updates-testing', latest=True)])
        client.send_request.assert_called_once_with('releases/', params={}, verb='GET')


class TestBodhiClient_get_releases:
    """
    Test the BodhiClient.get_releases() method.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies', mock.MagicMock())
    def test_get_releases(self):
        """Assert correct behavior from the get_releases() method."""
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(
            return_value={'releases': [{'candidate_tag': 'f25-updates-testing'},
                                       {'candidate_tag': 'f26-updates-testing'}]})

        results = client.get_releases(some_param='some_value')

        assert results == {'releases': [{'candidate_tag': 'f25-updates-testing'},
                                        {'candidate_tag': 'f26-updates-testing'}]
                           }
        client.send_request.assert_called_once_with(
            'releases/', params={'some_param': 'some_value'}, verb='GET')


class TestBodhiClient_parse_file:
    """
    Test the BodhiClient.parse_file() method.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.configparser.SafeConfigParser.read')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_parsing_invalid_file(self, exists, read, _load_cookies):
        """
        Test parsing an invalid update template file.
        """
        exists.return_value = True
        # This happens when we don't have permission to read the file.
        read.return_value = []
        client = bindings.BodhiClient()

        with pytest.raises(ValueError) as exc:
            client.parse_file("sad")

        assert str(exc.value) == 'Invalid input file: sad'

    @mock.patch('builtins.open', new_callable=mock.mock_open)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.os.path.exists')
    def test_parsing_valid_file(self, exists, _load_cookies, mock_open):
        """
        Test parsing a valid update template file
        """
        s = [
            "[fedora-workstation-backgrounds-1.1-1.fc26]\n",
            "# bugfix, security, enhancement, newpackage (required)\n",
            "type=bugfix\n",
            "\n",
            "# testing, stable\n",
            "request=testing\n",
            "\n",
            "# Bug numbers: 1234,9876\n",
            "bugs=123456,43212\n",
            "\n",
            "# Here is where you give an explanation of your update.\n",
            "notes=Initial Release\n",
            "\n",
            "# Update name\n",
            "display_name=fake update name\n",
            "\n",
            "# Enable request automation based on the stable/unstable karma thresholds\n",
            "autokarma=True\n",
            "stable_karma=3\n",
            "unstable_karma=-3\n",
            "\n",
            "# Automatically close bugs when this marked as stable\n",
            "close_bugs=True\n",
            "\n",
            "# Suggest that users restart after update\n",
            "suggest_reboot=False\n",
            ""]
        exists.return_value = True
        mock_open.return_value.readline.side_effect = s
        # Workaround for Python bug https://bugs.python.org/issue21258
        mock_open.return_value.__iter__ = lambda self: iter(self.readline, '')

        client = bindings.BodhiClient()
        updates = client.parse_file("sad")

        assert len(updates) == 1
        assert len(updates[0]) == 13
        assert updates[0]['close_bugs'] == True
        assert updates[0]['display_name'] == 'fake update name'
        assert updates[0]['unstable_karma'] == '-3'
        assert updates[0]['severity'] == 'unspecified'
        assert updates[0]['stable_karma'] == '3'
        assert updates[0]['builds'] == 'fedora-workstation-backgrounds-1.1-1.fc26'
        assert updates[0]['autokarma'] == 'True'
        assert updates[0]['suggest'] == 'unspecified'
        assert updates[0]['notes'] == 'Initial Release'
        assert updates[0]['request'] == 'testing'
        assert updates[0]['bugs'] == '123456,43212'
        assert updates[0]['type_'] == 'bugfix'
        assert updates[0]['type'] == 'bugfix'

    def test_parsing_nonexistent_file(self):
        """
        Test trying to parse a file that doesnt exist
        """
        client = bindings.BodhiClient()

        with pytest.raises(ValueError) as exc:
            client.parse_file("/tmp/bodhi-test-parsefile2")

        assert str(exc.value) == 'No such file or directory: /tmp/bodhi-test-parsefile2'


class TestBodhiClient_testable:
    """
    Test the BodhiClient.testable() method.
    """
    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies', mock.MagicMock())
    @mock.patch('bodhi.client.bindings.BodhiClient.get_koji_session')
    @mock.patch('bodhi.client.bindings.dnf')
    def test_testable(self, dnf, get_koji_session, mock_open):
        """Assert correct behavior from the testable() method."""
        fill_sack = mock.MagicMock()
        dnf.Base.return_value.fill_sack = fill_sack
        get_koji_session.return_value.listTagged.return_value = [
            {'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc26', 'nvr': 'bodhi-2.9.0-1.fc26'}]
        fill_sack.return_value.query.return_value.installed.return_value.filter.\
            return_value.run.return_value = ['bodhi-2.8.1-1.fc26']
        mock_open.return_value.__enter__.return_value.readlines.return_value = [
            'Fedora release 26 (Twenty Six)']
        client = bindings.BodhiClient()
        client.send_request = mock.MagicMock(
            return_value={'updates': [{'nvr': 'bodhi-2.9.0-1.fc26'}]})

        updates = client.testable()

        assert list(updates) == [{'nvr': 'bodhi-2.9.0-1.fc26'}]
        fill_sack.assert_called_once_with(load_system_repo=True)
        fill_sack.return_value.query.assert_called_once_with()
        fill_sack.return_value.query.return_value.installed.assert_called_once_with()
        fill_sack.return_value.query.return_value.installed.return_value.filter.\
            assert_called_once_with(name='bodhi', version='2.9.0', release='1.fc26')
        fill_sack.return_value.query.return_value.installed.return_value.filter.return_value.run.\
            assert_called_once_with()
        get_koji_session.return_value.listTagged.assert_called_once_with('f26-updates-testing',
                                                                         latest=True)
        client.send_request.assert_called_once_with(
            'updates/', params={'builds': 'bodhi-2.9.0-1.fc26'}, verb='GET')

    @mock.patch('bodhi.client.bindings.dnf', None)
    def test_testable_no_dnf(self):
        """Ensure that testable raises a RuntimeError if dnf is None."""
        client = bindings.BodhiClient()

        with pytest.raises(RuntimeError) as exc:
            list(client.testable())

        assert str(exc.value) == 'dnf is required by this method and is not installed.'


class TestGetKojiSession:
    """
    This class tests the get_koji_session method.
    """
    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.configparser.ConfigParser.readfp')
    @mock.patch("os.path.exists")
    @mock.patch("os.path.expanduser", return_value="/home/dudemcpants/")
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.koji.ClientSession')
    @mock.patch('bodhi.client.bindings.configparser.ConfigParser.get')
    def test_koji_conf_in_home_directory(self, get, koji, cookies,
                                         expanduser, exists, readfp, mock_open):
        """Test that if ~/.koji/config exists, we read the config from there first"""

        client = bindings.BodhiClient()
        exists.return_value = True
        client.get_koji_session()

        exists.assert_called_once_with("/home/dudemcpants/.koji/config")
        mock_open.assert_called_once_with("/home/dudemcpants/.koji/config")

    @mock.patch('builtins.open', create=True)
    @mock.patch('bodhi.client.bindings.configparser.ConfigParser.readfp')
    @mock.patch("os.path.exists")
    @mock.patch("os.path.expanduser", return_value="/home/dudemcpants/")
    @mock.patch('bodhi.client.bindings.BodhiClient._load_cookies')
    @mock.patch('bodhi.client.bindings.koji.ClientSession')
    @mock.patch('bodhi.client.bindings.configparser.ConfigParser.get')
    def test_koji_conf_not_in_home_directory(self, get, koji, cookies,
                                             expanduser, exists, readfp, mock_open):
        """Test that if ~/.koji.config doesn't exist, we read config from /etc/koji.conf"""

        client = bindings.BodhiClient()
        exists.return_value = False
        client.get_koji_session()

        exists.assert_called_once_with("/home/dudemcpants/.koji/config")
        mock_open.assert_called_once_with("/etc/koji.conf")


class TestBodhiClient_waive:
    """
    This class contains tests for BodhiClient.waive().
    """

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/waive-test-results',
                    status=404, msg='update not found'))
    def test_404_error(self, send_request, __init__):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with pytest.raises(bindings.UpdateNotFound) as exc:
            client.waive('bodhi-2.2.4-1.el7', comment='Expected failure', tests=None)

        assert exc.value.update == 'bodhi-2.2.4-1.el7'

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': None, 'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH)
    def test_successful_waive_some(self, send_request, __init__):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        response = client.waive(
            'bodhi-2.2.4-1.el7', comment='Expected failure',
            tests=('dist.rpmdeplint', 'fedora-atomic-ci')
        )

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': ('dist.rpmdeplint', 'fedora-atomic-ci'), 'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH)
    def test_successful_waive_all(self, send_request, __init__):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        response = client.waive('bodhi-2.2.4-1.el7', comment='Expected failure', tests=None)

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': None, 'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_other_ServerError(self, send_request, __init__):
        """
        Test for the case when a non-404 ServerError is raised.
        """
        server_error = fedora.client.ServerError(
            url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/waive-test-results',
            status=500, msg='Internal server error')
        send_request.side_effect = server_error
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with pytest.raises(fedora.client.ServerError) as exc:
            client.waive('bodhi-2.2.4-1.el7', comment='Expected failure', tests=None)

        assert exc.value is server_error

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': None, 'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)


class TestBodhiClient_trigger_tests:
    """
    This class contains tests for BodhiClient.trigger_tests().
    """

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/waive-test-results',
                    status=404, msg='update not found'))
    def test_404_error(self, send_request, __init__):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with pytest.raises(bindings.UpdateNotFound) as exc:
            client.trigger_tests('bodhi-2.2.4-1.el7')

        assert exc.value.update == 'bodhi-2.2.4-1.el7'

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/trigger-tests', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH)
    def test_successful_trigger(self, send_request, __init__):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        response = client.trigger_tests(
            'bodhi-2.2.4-1.el7')

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/trigger-tests', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_other_ServerError(self, send_request, __init__):
        """
        Test for the case when a non-404 ServerError is raised.
        """
        server_error = fedora.client.ServerError(
            url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/trigger-tests',
            status=500, msg='Internal server error')
        send_request.side_effect = server_error
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with pytest.raises(fedora.client.ServerError) as exc:
            client.trigger_tests('bodhi-2.2.4-1.el7')

        assert exc.value is server_error

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/trigger-tests', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)
