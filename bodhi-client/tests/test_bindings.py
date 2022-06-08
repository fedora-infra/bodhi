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
import os

from requests import HTTPError
import munch
import pytest

from bodhi.client import bindings, constants
from bodhi.client.oidcclient import OIDCClientError

from . import fixtures as client_test_data
from .utils import build_response, compare_output


class BodhiClientTestCase:
    def setup_method(self, method):
        self.oidcclient_patcher = mock.patch("bodhi.client.bindings.OIDCClient")
        self.oidcclient_class = self.oidcclient_patcher.start()

    def teardown_method(self, method):
        self.oidcclient_patcher.stop()


class TestBodhiClientBase(BodhiClientTestCase):

    def test_base_url_not_ends_in_slash(self):
        """
        If the base_url doesn't end in a slash, __init__() should append one.
        """
        client = bindings.BodhiClient(base_url='http://localhost:6543')

        assert client.base_url == 'http://localhost:6543/'

    def test_id_provider(self, mocker):
        """Test the id_provider parameter."""
        storage = mocker.patch("bodhi.client.bindings.JSONStorage")
        storage.return_value = mocker.Mock()

        client = bindings.BodhiClient(
            base_url='http://example.com/bodhi/', client_id='CLIENT_ID',
            id_provider='https://id.example.com/', staging=False)

        assert client.base_url == 'http://example.com/bodhi/'
        self.oidcclient_class.assert_called_with(
            "CLIENT_ID",
            constants.SCOPE,
            "https://id.example.com",
            storage=storage.return_value
        )
        storage.assert_called_with(os.path.expanduser("~/.config/bodhi/client.json"))
        assert client.csrf_token == ''

    def test_staging_true(self, mocker):
        """
        Test with staging set to True.
        """
        storage = mocker.patch("bodhi.client.bindings.JSONStorage")
        storage.return_value = mocker.Mock()

        client = bindings.BodhiClient(
            base_url='http://example.com/bodhi/', client_id='CLIENT_ID',
            id_provider='https://id.example.com/', staging=True)

        assert client.base_url == constants.STG_BASE_URL
        self.oidcclient_class.assert_called_with(
            constants.STG_CLIENT_ID,
            constants.SCOPE,
            constants.STG_IDP,
            storage=storage.return_value
        )
        assert client.csrf_token == ''


class TestBodhiClientAuth(BodhiClientTestCase):
    def setup_method(self, method):
        super().setup_method(method)
        self.oidc = mock.Mock(name="oidc")
        self.oidcclient_class.return_value = self.oidc

    def test_ensure_auth_ok(self):
        self.oidc.has_cookie.return_value = False
        self.oidc.request.return_value = build_response(200, "/login-token", "")
        client = bindings.BodhiClient(base_url='http://example.com/bodhi/')

        client.ensure_auth()

        self.oidc.ensure_auth.assert_called_once_with()
        self.oidc.request.assert_called_once_with(
            "GET", "http://example.com/bodhi/oidc/login-token"
        )
        self.oidc.login.assert_not_called()

    def test_ensure_auth_retry(self):
        self.oidc.has_cookie.return_value = False
        self.oidc.request.side_effect = [
            build_response(401, "/login-token", "nope"),
            build_response(401, "/login-token", "still no"),
            build_response(200, "/login-token", "fine."),
        ]
        client = bindings.BodhiClient(base_url='http://example.com/bodhi/')

        client.ensure_auth()

        expected_call = mock.call("GET", "http://example.com/bodhi/oidc/login-token")
        self.oidc.request.call_args_list == [expected_call, expected_call, expected_call]
        self.oidc.clear_auth.call_count == 2
        self.oidc.login.call_count == 2

    def test_ensure_auth_failure(self):
        self.oidc.has_cookie.return_value = False
        self.oidc.request.return_value = build_response(500, "/login-token", "wat?")
        client = bindings.BodhiClient(base_url='http://example.com/bodhi/')

        with pytest.raises(HTTPError):
            client.ensure_auth()

        self.oidc.request.assert_called_once_with(
            "GET", "http://example.com/bodhi/oidc/login-token"
        )
        self.oidc.login.assert_not_called()

    def test_send_request_ok(self, mocker):
        requests = mocker.patch("bodhi.client.bindings.requests")
        requests.request.return_value = build_response(200, "/url", '{"foo": "bar"}')

        client = bindings.BodhiClient(base_url='http://example.com/bodhi/')

        response = client.send_request("somewhere", "GET")

        requests.request.assert_called_once_with("GET", "http://example.com/bodhi/somewhere")
        self.oidc.request.assert_not_called()
        assert "foo" in response
        assert response.foo == "bar"

    def test_send_request_with_auth(self, mocker):
        self.oidc.request.return_value = build_response(200, "/url", '{"foo": "bar"}')
        client = bindings.BodhiClient(base_url='http://example.com/bodhi/')

        client.send_request("somewhere", "GET", auth=True)

        self.oidc.request.assert_called_once_with("GET", "http://example.com/bodhi/somewhere")
        self.oidc.ensure_auth.assert_called_once_with()

    def test_send_request_error(self, mocker):
        response = build_response(500, "/url", "error")
        requests = mocker.patch("bodhi.client.bindings.requests")
        self.oidc.request.return_value = requests.request.return_value = response
        client = bindings.BodhiClient(base_url='http://example.com/bodhi/')

        with pytest.raises(bindings.BodhiClientException) as exc:
            client.send_request("somewhere", "GET")
        assert str(exc.value) == "error"
        with pytest.raises(bindings.BodhiClientException) as exc:
            client.send_request("somewhere", "GET", auth=True)
        assert str(exc.value) == "error"

    def test_send_request_failure(self, mocker):
        failure = OIDCClientError("Something went wrong")
        requests = mocker.patch("bodhi.client.bindings.requests")
        self.oidc.request.side_effect = requests.request.side_effect = failure
        client = bindings.BodhiClient(base_url='http://example.com/bodhi/')

        with pytest.raises(bindings.BodhiClientException) as exc:
            client.send_request("somewhere", "GET")
        assert str(exc.value) == "Something went wrong"
        with pytest.raises(bindings.BodhiClientException) as exc:
            client.send_request("somewhere", "GET", auth=True)
        assert str(exc.value) == "Something went wrong"


class TestComment(BodhiClientTestCase):
    def test_comment(self, mocker):
        """
        Test the comment() method.
        """
        client = bindings.BodhiClient()
        client.csrf_token = 'a token'
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.comment('bodhi-2.4.0-1.fc25', 'It ate my cat!', karma=-1)

        assert response == 'response'
        client.send_request.assert_called_once_with(
            'comments/', verb='POST', auth=True,
            data={'update': 'bodhi-2.4.0-1.fc25', 'text': 'It ate my cat!', 'karma': -1,
                  'csrf_token': 'a token'})


class TestComposeStr(BodhiClientTestCase):
    def test_error_message(self, mocker):
        """Assert that an error message gets rendered in the long form."""
        mocker.patch.dict(client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0],
                          {'error_message': 'some error'})
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

    def test_non_security_update(self, mocker):
        """Non-security updates should not have a leading *."""
        mocker.patch.dict(client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0],
                          {'security': False})
        s = bindings.BodhiClient.compose_str(
            client_test_data.EXAMPLE_COMPOSES_MUNCH['composes'][0], minimal=True)

        assert s == ' EPEL-7-stable  :   2 updates (requested) '


class TestCSRF(BodhiClientTestCase):
    def test_with_csrf_token(self, mocker):
        """
        Test the method when csrf_token is set.
        """
        client = bindings.BodhiClient()
        client.csrf_token = 'a token'
        client.send_request = mocker.MagicMock(return_value='response')

        csrf = client.csrf()

        assert csrf == 'a token'
        assert client.send_request.call_count == 0

    def test_without_csrf_token_without_cookies(self, mocker):
        """
        Test the method when csrf_token is not set.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value={'csrf_token': 'a great token'})

        csrf = client.csrf()

        assert csrf == 'a great token'
        assert client.csrf_token == 'a great token'
        client.send_request.assert_called_once_with('csrf', verb='GET', auth=True)


class TestLatestBuilds(BodhiClientTestCase):
    def test_latest_builds(self, mocker):
        """
        Test latest_builds().
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='bodhi-2.4.0-1.fc25')

        latest_builds = client.latest_builds('bodhi')

        assert latest_builds == 'bodhi-2.4.0-1.fc25'
        client.send_request.assert_called_once_with('latest_builds', params={'package': 'bodhi'})


class TestCompose(BodhiClientTestCase):
    def test_get_compose_404_error(self, mocker):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        send_request.side_effect = HTTPError(
            response=build_response(
                404, "http://example.com/tests/composes/EPEL-7/stable", "update not found"
            )
        )

        with pytest.raises(bindings.ComposeNotFound) as exc:
            client.get_compose('EPEL-7', 'stable')

        assert exc.value.release == 'EPEL-7'
        assert exc.value.request == 'stable'

        send_request.assert_called_once_with('composes/EPEL-7/stable', verb='GET')

    def test_get_compose_successful_request(self, mocker):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        send_request.return_value = client_test_data.EXAMPLE_COMPOSE_MUNCH

        response = client.get_compose('EPEL-7', 'stable')

        assert response == client_test_data.EXAMPLE_COMPOSE_MUNCH
        send_request.assert_called_once_with('composes/EPEL-7/stable', verb='GET')

    def test_get_compose_other_http_error(self, mocker):
        """
        Test for the case when a non-404 http error is raised.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        server_error = HTTPError(
            response=build_response(
                500, "http://example.com/tests/composes/EPEL-7/stable", "Internal server error"
            )
        )
        send_request.side_effect = server_error

        with pytest.raises(HTTPError) as exc:
            client.get_compose('EPEL-7', 'stable')

        assert exc.value is server_error

        send_request.assert_called_once_with('composes/EPEL-7/stable', verb='GET')

    def test_list_composes(self, mocker):
        """Assert a correct call to send_request() from list_composes()."""
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='some_composes')

        composes = client.list_composes()

        assert composes == 'some_composes'
        client.send_request.assert_called_once_with('composes/', verb='GET')


class TestListOverrides(BodhiClientTestCase):
    def test_with_user(self, mocker):
        """
        Test with the user parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(user='bowlofeggs')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'user': 'bowlofeggs'})

    def test_without_parameters(self, mocker):
        """
        Test without the parameters.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides()

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET', params={})

    def test_with_package(self, mocker):
        """
        Test with the package parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(packages='bodhi')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'packages': 'bodhi'})

    def test_with_expired(self, mocker):
        """
        Test --expired with the expired/active click boolean parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(expired=True)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'expired': True})

    def test_with_active(self, mocker):
        """
        Test --active with the expired/active click boolean parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(expired=False)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'expired': False})

    def test_with_releases(self, mocker):
        """
        Test with the releases parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(releases='F24')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'releases': 'F24'})

    def test_list_overrides_with_builds(self, mocker):
        """
        Test with the builds parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(builds='python-1.5.6-3.fc26')

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'builds': 'python-1.5.6-3.fc26'})

    def test_list_overrides_with_rows_per_page(self, mocker):
        """
        Test with the rows_per_page parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(rows_per_page=10)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'rows_per_page': 10})

    def test_list_overrides_with_page(self, mocker):
        """
        Test with the page parameter.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='response')

        response = client.list_overrides(page=5)

        assert response == 'response'
        client.send_request.assert_called_once_with('overrides/', verb='GET',
                                                    params={'page': 5})


class TestOverrideStr(BodhiClientTestCase):
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


class TestQuery(BodhiClientTestCase):
    def test_with_bugs_empty_string(self, mocker):
        """
        Test with the bugs kwargs set to an empty string.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(builds='bodhi-2.4.0-1.fc26', bugs='')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26', 'bugs': None})

    def test_with_limit(self, mocker):
        """
        Assert that the limit kwargs gets translated to rows_per_page correctly.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(builds='bodhi-2.4.0-1.fc26', limit=50)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26', 'rows_per_page': 50})

    def test_with_mine_false(self, mocker):
        """
        Assert correct behavior when the mine kwargs is False.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(builds='bodhi-2.4.0-1.fc26', mine=False)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26', 'mine': False})

    def test_with_mine_true(self, mocker):
        """
        Assert correct behavior when the mine kwargs is True.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
        client.oidc.username = 'bowlofeggs'

        result = client.query(builds='bodhi-2.4.0-1.fc26', mine=True)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET',
            params={'builds': 'bodhi-2.4.0-1.fc26', 'mine': True, 'user': 'bowlofeggs'})

    def test_with_mine_no_username(self, mocker):
        """
        Assert correct behavior when the mine kwargs is True but we are not authentified.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
        client.oidc.username = None

        with pytest.raises(bindings.BodhiClientException) as exc:
            client.query(builds='bodhi-2.4.0-1.fc26', mine=True)
        assert str(exc.value) == "Could not get user info."

    def test_with_package_el_build(self, mocker):
        """
        Test with the package arg expressed as an el7 build.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(package='bodhi-2.4.0-1.el7')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.el7'})

    def test_with_package_epel_id(self, mocker):
        """
        Test with the package arg expressed as a EPEL update id.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(package='FEDORA-EPEL-2017-c3b112eb9e')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'updateid': 'FEDORA-EPEL-2017-c3b112eb9e'})

    def test_with_package_fc_build(self, mocker):
        """
        Test with the package arg expressed as a fc26 build.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(package='bodhi-2.4.0-1.fc26')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'builds': 'bodhi-2.4.0-1.fc26'})

    def test_with_package_fedora_id(self, mocker):
        """
        Test with the package arg expressed as a Fedora update id.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(package='FEDORA-2017-52506b30d4')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'updateid': 'FEDORA-2017-52506b30d4'})

    def test_with_package_name(self, mocker):
        """
        Test with the package arg expressed as a package name.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(package='bodhi')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi'})

    def test_with_release_list(self, mocker):
        """
        Test with a 'release' kwarg set to a list.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', release=['f27'])

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'releases': ['f27']})

    def test_with_release_str(self, mocker):
        """
        Test with a 'release' kwarg set to a str.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', release='f26')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'releases': ['f26']})

    def test_with_type_(self, mocker):
        """
        Test with the type_ kwarg.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', type_='security')

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'type': 'security'})

    def test_query_with_rows_per_page(self, mocker):
        """
        Test with the 'rows_per_page' kwarg.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', rows_per_page=10)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'rows_per_page': 10})

    def test_query_with_page(self, mocker):
        """
        Test with the 'page' kwarg.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')

        result = client.query(packages='bodhi', page=5)

        assert result == 'return_value'
        client.send_request.assert_called_once_with(
            'updates/', verb='GET', params={'packages': 'bodhi', 'page': 5})


class TestSave(BodhiClientTestCase):
    def test_save_with_type_(self, mocker):
        """
        Assert that save() handles type_ as a kwargs for backwards compatibility.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
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

    def test_without_type_(self, mocker):
        """
        Assert correct operation when type_ isn't given.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        kwargs = {
            'builds': ['bodhi-2.4.0-1.fc26'], 'type': 'enhancement', 'notes': 'This is a test',
            'request': 'testing', 'autokarma': True, 'stable_karma': 3, 'unstable_karma': -3,
            'severity': 'low'}

        response = client.save(**kwargs)

        assert response == 'return_value'
        kwargs['csrf_token'] = 'a token'
        client.send_request.assert_called_once_with('updates/', verb='POST', auth=True, data=kwargs)


class TestSaveOverride(BodhiClientTestCase):
    def test_save_override(self, mocker):
        """
        Test the save_override() method.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
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

    def test_save_override_expiration_date(self, mocker):
        """
        Test the save_override() method with an explicit expiration date.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        now = datetime.utcnow()
        response = client.save_override(nvr='python-pyramid-1.5.6-3.el7',
                                        expiration_date=now,
                                        notes='This is needed to build bodhi-2.4.0.')

        assert response == 'return_value'
        client.send_request.assert_called_once_with(
            'overrides/', verb='POST', auth=True,
            data={'nvr': 'python-pyramid-1.5.6-3.el7',
                  'expiration_date': now,
                  'csrf_token': 'a token', 'notes': 'This is needed to build bodhi-2.4.0.'})

    def test_save_override_no_expiration(self, mocker):
        """
        Test the save_override() method without duration or expiration date.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        with pytest.raises(TypeError):
            client.save_override(
                nvr='python-pyramid-1.5.6-3.el7',
                notes='This is needed to build bodhi-2.4.0.'
            )

    def test_save_override_both_expirations(self, mocker):
        """
        Test the save_override() method with duration and expiration date.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
        client.csrf_token = 'a token'
        now = datetime.utcnow()
        with pytest.raises(TypeError):
            client.save_override(
                nvr='python-pyramid-1.5.6-3.el7',
                notes='This is needed to build bodhi-2.4.0.',
                duration=1,
                expiration_date=now,
            )

    def test_save_override_edit(self, mocker):
        """
        Test the save_override() method with the edit argument.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
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

    def test_save_override_expired(self, mocker):
        """
        Test the save_override() method with the edit argument.
        """
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(return_value='return_value')
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


class TestRequest(BodhiClientTestCase):
    def test_request_404_error(self, mocker):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient()
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        send_request.side_effect = HTTPError(
            response=build_response(
                404,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/request",
                "update not found"
            )
        )

        with pytest.raises(bindings.UpdateNotFound) as exc:
            client.request('bodhi-2.2.4-1.el7', 'revoke')

        assert exc.value.update == 'bodhi-2.2.4-1.el7'

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-1.el7'})

    def test_request_successful_request(self, mocker):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient()
        send_request = mocker.patch.object(client, "send_request")
        send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH
        client.csrf_token = 'a_csrf_token'

        response = client.request('bodhi-2.2.4-1.el7', 'revoke')

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-1.el7'})

    def test_request_other_http_error(self, mocker):
        """
        Test for the case when a non-404 http error is raised.
        """
        client = bindings.BodhiClient()
        send_request = mocker.patch.object(client, "send_request")
        client.csrf_token = 'a_csrf_token'
        server_error = HTTPError(
            response=build_response(
                500,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/request",
                "Internal server error",
            )
        )
        send_request.side_effect = server_error

        with pytest.raises(HTTPError) as exc:
            client.request('bodhi-2.2.4-1.el7', 'revoke')

        assert exc.value is server_error

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': 'revoke',
                  'update': 'bodhi-2.2.4-1.el7'})


class TestUpdateStr(BodhiClientTestCase):
    def test_bugs(self, mocker):
        """Ensure correct output when there are bugs on the update."""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'bugs': [{'bug_id': 1234, 'title': 'it broke'}, {'bug_id': 1235, 'title': 'halp'}]}
        )
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(
            text,
            client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
                'Autotime: True', 'Autotime: True\n   Bugs: 1234 - it broke\n    : 1235 - halp'))

    def test_minimal(self, mocker):
        """Ensure correct output when minimal is True."""
        mock_datetime = mocker.patch("bodhi.client.bindings.datetime.datetime")
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    def test_minimal_not_pushed(self, mocker):
        """Ensure correct output when minimal is True and not yet pushed."""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'date_pushed': '', 'pushed': False, 'status': 'pending'}
        )
        mock_datetime = mocker.patch("bodhi.client.bindings.datetime.datetime")
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 5, 23, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        rpm        pending   '
                           '2016-10-05 (0)')
        assert text == expected_output

    def test_minimal_type_security(self, mocker):
        """Ensure correct output when minimal is True and type security"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'type': 'security'}
        )
        mock_datetime = mocker.patch("bodhi.client.bindings.datetime.datetime")
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = ('*bodhi-2.2.4-1.el7                        rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    def test_minimal_with_multiple_builds(self, mocker):
        """Ensure correct output when minimal is True, and multiple builds"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'builds': [
                {'epoch': 0, 'nvr': 'bodhi-2.2.4-1.el7', 'signed': True},
                {'epoch': 0, 'nvr': 'bodhi-pants-2.2.4-1.el7', 'signed': True}
            ]}
        )
        mock_datetime = mocker.patch("bodhi.client.bindings.datetime.datetime")
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime
        client = bindings.BodhiClient()

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        rpm        stable    '
                           '2016-10-21 (2)\n  bodhi-pants-2.2.4-1.el7')
        assert text == expected_output

    def test_minimal_no_builds(self, mocker):
        """Ensure correct output when minimal is True, and there are no builds"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'builds': [], 'title': 'update-title'}
        )
        mock_datetime = mocker.patch("bodhi.client.bindings.datetime.datetime")
        client = bindings.BodhiClient()
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' update-title                             rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    def test_minimal_no_title(self, mocker):
        """Ensure correct output when minimal is True, and there are neither a title nor builds"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'title': None, 'builds': []}
        )
        mock_datetime = mocker.patch("bodhi.client.bindings.datetime.datetime")
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime
        client = bindings.BodhiClient()

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' FEDORA-EPEL-2016-3081a94111              '
                           'rpm        stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    def test_minimal_no_content_type(self, mocker):
        """Ensure correct output when minimal is True, and and there is no content-type"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'content_type': None}
        )
        mock_datetime = mocker.patch("bodhi.client.bindings.datetime.datetime")
        mock_datetime.utcnow = mock.Mock(return_value=datetime(2016, 10, 24, 12, 0, 0))
        mock_datetime.strptime = datetime.strptime
        client = bindings.BodhiClient()

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH, minimal=True)

        expected_output = (' bodhi-2.2.4-1.el7                        '
                           'unspecified  stable    '
                           '2016-10-21 (2)')
        assert text == expected_output

    def test_request_stable(self, mocker):
        """Ensure correct output when the update is request stable."""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'request': 'stable'}
        )
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)
        print("This is", text)

        assert compare_output(
            text,
            client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
                'Autotime: True', 'Autotime: True\n     Request: stable'))

    def test_severity(self, mocker):
        """Test that severity is rendered."""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'Severity: unspecified' in text

    def test_with_autokarma_set(self, mocker):
        """
        Ensure correct operation when autokarma is True..
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(text, client_test_data.EXPECTED_UPDATE_OUTPUT)

    def test_with_autokarma_unset(self, mocker):
        """
        Ensure correct operation when autokarma is False.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")
        update = copy.deepcopy(client_test_data.EXAMPLE_UPDATE_MUNCH)
        # Set the update's autokarma and to False.
        update.autokarma = False

        text = client.update_str(update)

        expected_output = client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
            'Autokarma: True  [-3, 3]', 'Autokarma: False  [-3, 3]')
        assert compare_output(text, expected_output)

    def test_autotime_set(self, mocker):
        """
        Ensure correct operation when autotime is True.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(text, client_test_data.EXPECTED_UPDATE_OUTPUT)

    def test_autotime_unset(self, mocker):
        """
        Ensure correct operation when autotime is False.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")
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

    def test_update_with_unicode_comment(self, mocker):
        """Ensure unicode content in update comments is correctly handled"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH.comments[0],
            {'text': 'This comment contains a unicode char ☺. '}
        )
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert compare_output(
            text,
            client_test_data.EXPECTED_UPDATE_OUTPUT.replace(
                'This update has been submitted for testing by bowlofeggs.',
                'This comment contains a unicode char ☺.'))

    def test_update_with_unicode_note(self, mocker):
        """Ensure unicode content in update notes is correctly handled"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'notes': 'This note contains a unicode char ☺'}
        )
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'Notes: This note contains a unicode char ☺' in text

    def test_ci_status_errors(self, mocker):
        """Ensure that ci error is displayed"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status = mocker.patch.object(client, "get_test_status")
        get_test_status.return_value = munch.Munch(
            {'errors': [munch.Munch({'description': 'bar'})]})

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'CI Status: bar\n' in text

    def test_ci_status_failure(self, mocker):
        """Ensure that ci is not displayed when it fails"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status = mocker.patch.object(client, "get_test_status")
        get_test_status.side_effect = HTTPError("testing error")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'CI Status' not in text

    def test_ci_status(self, mocker):
        """Ensure that ci information is displayed"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status = mocker.patch.object(client, "get_test_status")
        get_test_status.return_value = munch.Munch(
            {'decision': munch.Munch({'summary': 'no tests required', 'waivers': []})}
        )

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'CI Status: no tests required\n' in text

    def test_waived_tests(self, mocker):
        """Ensure that information about waived tests is rendered"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status = mocker.patch.object(client, "get_test_status")
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

    def test_ci_status_new_format(self, mocker):
        """Ensure that ci information is displayed with Greenwave's new format"""
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        get_test_status = mocker.patch.object(client, "get_test_status")
        get_test_status.return_value = munch.Munch(
            {'decisions': [munch.Munch({'summary': 'no tests required', 'waivers': []})]}
        )

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'CI Status: no tests required\n' in text

    def test_notes_multiline(self, mocker):
        """Ensure that multiline notes are rendered"""
        mocker.patch.dict(
            client_test_data.EXAMPLE_UPDATE_MUNCH,
            {'notes': 'This note contains:\n* multiline formatting\n* bullet points\n\n'}
        )
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        mocker.patch.object(client, "send_request")

        text = client.update_str(client_test_data.EXAMPLE_UPDATE_MUNCH)

        assert 'Notes: This note contains:\n' in text
        assert '     : * multiline formatting\n' in text
        assert '     : * bullet points\n' in text


class TestErrorHandled:
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

    def test_retry_on_captcha_key_failure(self, mocker):
        """
        Test the decorator when the wrapped method returns a captch_key error.

        This test ensures that the decorator will retry the wrapped method if it returns a
        captcha_key error, after clearing cookies and the csrf token.

        This test was written to assert the fix for
        https://github.com/fedora-infra/bodhi/issues/1787
        """
        a_fake_self = mocker.MagicMock()
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

        a_fake_self.clear_auth.assert_called_once_with()
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
    def test_updatenotfound(self):
        """
        Assert that __init__() works properly.
        """
        exc = bindings.UpdateNotFound('bodhi-2.2.4-1.el7')

        assert exc.update == 'bodhi-2.2.4-1.el7'
        assert type(exc.update) == str

    def test_updatenotfound_str(self):
        """
        Assert that __str__() works properly.
        """
        exc = bindings.UpdateNotFound('bodhi-2.2.4-1.el7')

        assert str(exc.update) == 'bodhi-2.2.4-1.el7'
        assert type(str(exc.update)) == str
        assert str(exc) == 'Update not found: bodhi-2.2.4-1.el7'


class TestCandidates(BodhiClientTestCase):
    def test_candidates_failure(self, mocker, caplog):
        """Ensure correct handling when talking to Koji raises an Exception."""
        client = bindings.BodhiClient()
        client.oidc.username = 'bowlofeggs'
        get_koji_session = mocker.patch.object(client, "get_koji_session")
        get_koji_session.return_value.listTagged.side_effect = [
            [
                {'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc25',
                 'nvr': 'bodhi-2.9.0-1.fc25', 'owner_name': 'bowlofeggs'},
                {'name': 'ipsilon', 'version': '2.0.2', 'release': '1.fc25',
                 'nvr': 'ipsilon-2.0.2-1.fc25', 'owner_name': 'puiterwijk'}
            ],
            IOError("Bet you didn't expect this.")
        ]
        mocker.patch.object(client, "send_request", return_value={
            'releases': [
                {'candidate_tag': 'f25-updates-testing'},
                {'candidate_tag': 'f26-updates-testing'}
            ]
        })

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
        expected_error = (
            "Unable to query candidate builds for {'candidate_tag': 'f26-updates-testing'}"
        )
        assert expected_error in caplog.messages

    def test_candidates_success(self, mocker):
        """Ensure correct behavior when there are no errors talking to Koji."""
        client = bindings.BodhiClient()
        client.oidc.username = 'bowlofeggs'
        get_koji_session = mocker.patch.object(client, "get_koji_session")
        get_koji_session.return_value.listTagged.side_effect = [
            [{'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc25', 'nvr': 'bodhi-2.9.0-1.fc25',
              'owner_name': 'bowlofeggs'},
             {'name': 'ipsilon', 'version': '2.0.2', 'release': '1.fc25',
              'nvr': 'ipsilon-2.0.2-1.fc25', 'owner_name': 'puiterwijk'}],
            [{'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc26', 'nvr': 'bodhi-2.9.0-1.fc26',
              'owner_name': 'bowlofeggs'}]]
        mocker.patch.object(client, "send_request", return_value={
            'releases': [
                {'candidate_tag': 'f25-updates-testing'},
                {'candidate_tag': 'f26-updates-testing'}
            ]
        })

        results = client.candidates()

        assert results == [
            {
                'release': '1.fc25',
                'version': '2.9.0',
                'name': 'bodhi',
                'owner_name': 'bowlofeggs',
                'nvr': 'bodhi-2.9.0-1.fc25'
            },
            {
                'release': '1.fc26',
                'version': '2.9.0',
                'name': 'bodhi',
                'owner_name': 'bowlofeggs',
                'nvr': 'bodhi-2.9.0-1.fc26'
            }
        ]
        get_koji_session.assert_called_once_with()
        assert (
            get_koji_session.return_value.listTagged.mock_calls
            == [mock.call('f25-updates-testing', latest=True),
                mock.call('f26-updates-testing', latest=True)])
        client.send_request.assert_called_once_with('releases/', params={}, verb='GET')


class TestGetReleases(BodhiClientTestCase):
    def test_get_releases(self, mocker):
        """Assert correct behavior from the get_releases() method."""
        client = bindings.BodhiClient()
        client.send_request = mocker.MagicMock(
            return_value={'releases': [{'candidate_tag': 'f25-updates-testing'},
                                       {'candidate_tag': 'f26-updates-testing'}]})

        results = client.get_releases(some_param='some_value')

        assert results == {
            'releases': [
                {'candidate_tag': 'f25-updates-testing'},
                {'candidate_tag': 'f26-updates-testing'}
            ]
        }
        client.send_request.assert_called_once_with(
            'releases/', params={'some_param': 'some_value'}, verb='GET')


class TestParseFile(BodhiClientTestCase):
    def test_parsing_invalid_file(self, tmpdir, mocker):
        """
        Test parsing an invalid update template file.
        """
        filepath = tmpdir.join("f.ini")
        open(filepath, "w").close()
        cp_read = mocker.patch("bodhi.client.bindings.configparser.ConfigParser.read")
        # This happens when we don't have permission to read the file.
        # We can't just remove the permissions because the unit tests run as root in bodhi-ci.
        cp_read.return_value = []
        client = bindings.BodhiClient()

        with pytest.raises(ValueError) as exc:
            try:
                result = client.parse_file(filepath)
            except Exception as e:
                print(e)
                raise
            print(result)

        assert str(exc.value) == f'Invalid input file: {filepath}'

    def test_parsing_valid_file(self, tmpdir):
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

        filepath = tmpdir.join("f.ini")
        with open(filepath, "w") as f:
            f.writelines(s)
        client = bindings.BodhiClient()
        updates = client.parse_file(filepath)

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


class TestTestable(BodhiClientTestCase):
    def test_testable(self, mocker):
        """Assert correct behavior from the testable() method."""
        dnf = mocker.patch("bodhi.client.bindings.dnf")
        fill_sack = mock.MagicMock()
        dnf.Base.return_value.fill_sack = fill_sack
        fill_sack.return_value.query.return_value.installed.return_value.filter.\
            return_value.run.return_value = ['bodhi-2.8.1-1.fc26']

        client = bindings.BodhiClient()
        get_koji_session = mocker.patch.object(client, "get_koji_session")
        get_koji_session.return_value.listTagged.return_value = [
            {'name': 'bodhi', 'version': '2.9.0', 'release': '1.fc26', 'nvr': 'bodhi-2.9.0-1.fc26'}]

        client.send_request = mock.MagicMock(
            return_value={'updates': [{'nvr': 'bodhi-2.9.0-1.fc26'}]})

        mock_open = mocker.patch('builtins.open', create=True)
        mock_open.return_value.__enter__.return_value.readlines.return_value = [
            'Fedora release 26 (Twenty Six)']

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

    def test_testable_no_dnf(self, mocker):
        """Ensure that testable raises a RuntimeError if dnf is None."""
        mocker.patch("bodhi.client.bindings.dnf", None)

        client = bindings.BodhiClient()

        with pytest.raises(RuntimeError) as exc:
            list(client.testable())

        assert str(exc.value) == 'dnf is required by this method and is not installed.'


class TestKojiSession(BodhiClientTestCase):
    def test_koji_conf_in_home_directory(self, mocker, tmpdir):
        """Test that if ~/.koji/config exists, we read the config from there first"""
        koji = mocker.patch("bodhi.client.bindings.koji.ClientSession")
        mocker.patch("os.path.expanduser", return_value=tmpdir)
        os.mkdir(tmpdir.join(".koji"))
        with open(tmpdir.join(".koji", "config"), "w") as f:
            f.write("[koji]\nserver = foobar\n")
        client = bindings.BodhiClient()
        client.get_koji_session()
        koji.assert_called_with("foobar")

    def test_koji_conf_not_in_home_directory(self, mocker, tmpdir):
        """Test that if ~/.koji/config doesn't exist, we read config from /etc/koji.conf"""
        koji = mocker.patch("bodhi.client.bindings.koji.ClientSession")
        with open(tmpdir.join("etckojiconf"), "w") as f:
            f.write("[koji]\nserver = foobar\n")

        client = bindings.BodhiClient()
        with open(tmpdir.join("etckojiconf")) as f:
            mock_open = mocker.patch('builtins.open', create=True)
            mock_open.return_value = f
            # read_file = mocker.patch('bodhi.client.bindings.configparser.ConfigParser.read_file')
            client.get_koji_session()
            mock_open.assert_called_once_with("/etc/koji.conf")
        koji.assert_called_with("foobar")


class TestWaive(BodhiClientTestCase):
    def test_waive_404_error(self, mocker):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        server_error = HTTPError(
            response=build_response(
                404,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/waive-test-results",
                "update not found",
            )
        )
        send_request.side_effect = server_error

        with pytest.raises(bindings.UpdateNotFound) as exc:
            client.waive('bodhi-2.2.4-1.el7', comment='Expected failure', tests=None)

        assert exc.value.update == 'bodhi-2.2.4-1.el7'

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': None, 'update': 'bodhi-2.2.4-1.el7'})

    def test_successful_waive_some(self, mocker):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH

        response = client.waive(
            'bodhi-2.2.4-1.el7', comment='Expected failure',
            tests=('dist.rpmdeplint', 'fedora-atomic-ci')
        )

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': ('dist.rpmdeplint', 'fedora-atomic-ci'), 'update': 'bodhi-2.2.4-1.el7'})

    def test_successful_waive_all(self, mocker):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH

        response = client.waive('bodhi-2.2.4-1.el7', comment='Expected failure', tests=None)

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': None, 'update': 'bodhi-2.2.4-1.el7'})

    def test_waive_other_http_error(self, mocker):
        """
        Test for the case when a non-404 http error is raised.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        server_error = HTTPError(
            response=build_response(
                500,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/waive-test-results",
                "Internal server error",
            )
        )
        send_request.side_effect = server_error

        with pytest.raises(HTTPError) as exc:
            client.waive('bodhi-2.2.4-1.el7', comment='Expected failure', tests=None)

        assert exc.value is server_error

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/waive-test-results', verb='POST', auth=True,
            data={'comment': 'Expected failure', 'csrf_token': 'a_csrf_token',
                  'tests': None, 'update': 'bodhi-2.2.4-1.el7'})


class TestTriggerTests(BodhiClientTestCase):
    def test_trigger_tests_404_error(self, mocker):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        server_error = HTTPError(
            response=build_response(
                404,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/trigger-tests",
                "update not found",
            )
        )
        send_request.side_effect = server_error

        with pytest.raises(bindings.UpdateNotFound) as exc:
            client.trigger_tests('bodhi-2.2.4-1.el7')

        assert exc.value.update == 'bodhi-2.2.4-1.el7'

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/trigger-tests', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'bodhi-2.2.4-1.el7'})

    def test_successful_trigger(self, mocker):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        send_request.return_value = client_test_data.EXAMPLE_UPDATE_MUNCH

        response = client.trigger_tests(
            'bodhi-2.2.4-1.el7')

        assert response == client_test_data.EXAMPLE_UPDATE_MUNCH
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/trigger-tests', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'bodhi-2.2.4-1.el7'})

    def test_trigger_tests_other_http_error(self, mocker):
        """
        Test for the case when a non-404 http error is raised.
        """
        client = bindings.BodhiClient()
        client.base_url = 'http://example.com/tests/'
        client.csrf_token = 'a_csrf_token'
        send_request = mocker.patch.object(client, "send_request")
        server_error = HTTPError(
            response=build_response(
                500,
                "http://example.com/tests/updates/bodhi-2.2.4-99.el7/trigger-tests",
                "Internal server error",
            )
        )
        send_request.side_effect = server_error

        with pytest.raises(HTTPError) as exc:
            client.trigger_tests('bodhi-2.2.4-1.el7')

        assert exc.value is server_error

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/trigger-tests', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token',
                  'update': 'bodhi-2.2.4-1.el7'})
