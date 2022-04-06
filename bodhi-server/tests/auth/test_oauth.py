"""
Adapted from:
https://github.com/lepture/authlib/blob/master/tests/django/test_client/test_oauth_client.py
"""

from unittest import mock

from authlib import __version__ as authlib_version
from authlib.common.urls import url_decode, urlparse
from authlib.integrations.base_client import OAuthError
from authlib.jose import jwk
from authlib.oidc.core.grants.util import generate_id_token
from packaging.version import parse as parse_version
from pyramid import testing
import pytest

from bodhi.server.auth import OAuth
from bodhi.server.auth.oauth import TokenUpdate

from .. import base
from ..utils import get_bearer_token, mock_send_value
from .utils import get_session_data, set_session_data


class TestOAuthRegistry(base.BasePyTestCase):
    """Test the Pyramid-specific OAuth integration."""

    def test_register(self):
        """Test plain registration."""

        oauth = OAuth()
        oauth.register(
            "dev",
            client_id='dev',
            client_secret='dev',
            client_kwargs={
                'scope': "openid email profile",
                'token_endpoint_auth_method': 'client_secret_post',
            },
        )
        assert oauth.dev.name == 'dev'
        assert oauth.dev.client_id == 'dev'
        assert oauth.dev.client_secret == 'dev'

    def test_register_from_settings(self):
        """Test getting the registration settings from Pyramid"""
        self.config.add_settings({
            "oidc.dev.client_id": "test-client-id",
            "oidc.dev.client_secret": "test-client-secret",
        })
        oauth = OAuth()
        oauth.register(
            "dev",
            client_kwargs={
                'scope': "openid email profile",
                'token_endpoint_auth_method': 'client_secret_post',
            },
        )
        assert oauth.dev.name == 'dev'
        assert oauth.dev.client_id == 'test-client-id'
        assert oauth.dev.client_secret == 'test-client-secret'


class TestOAuth1(base.BasePyTestCase):
    """Test OAuth1 authentication"""

    def test_oauth1_authorize(self):
        request = testing.DummyRequest(path="/login")

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            request_token_url='https://i.b/request-token',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
        )

        with mock.patch('requests.sessions.Session.send') as send:
            send.return_value = mock_send_value('oauth_token=foo&oauth_verifier=baz')

            resp = client.authorize_redirect(request)
            assert resp.status_code == 302
            url = resp.headers.get('location')
            assert 'oauth_token=foo' in url

        parsed_url = urlparse.urlparse(url)
        request2 = testing.DummyRequest(
            path=parsed_url.path,
            params=dict(urlparse.parse_qsl(parsed_url.query))
        )
        request2.session = request.session
        with mock.patch('requests.sessions.Session.send') as send:
            send.return_value = mock_send_value('oauth_token=a&oauth_token_secret=b')
            token = client.authorize_access_token(request2)
            assert token['oauth_token'] == 'a'

    @pytest.mark.skipif(
        parse_version(authlib_version) < parse_version("1.0.0"),
        reason="Only on Authlib >= 1.0"
    )
    def test_oauth1_authorize_no_state(self):
        request = testing.DummyRequest(path="/login")

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            request_token_url='https://i.b/request-token',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
        )
        request = testing.DummyRequest(
            path="/oauth1",
            params={}
        )
        with pytest.raises(OAuthError) as exc:
            client.authorize_access_token(request)
        assert exc.value.description == 'Missing "oauth_token" parameter'

    @pytest.mark.skipif(
        parse_version(authlib_version) < parse_version("1.0.0"),
        reason="Only on Authlib >= 1.0"
    )
    def test_oauth1_authorize_no_data(self):
        request = testing.DummyRequest(path="/login")

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            request_token_url='https://i.b/request-token',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
        )

        request = testing.DummyRequest(
            path="/oauth1",
            params={"oauth_token": "foo", "state": "S"}
        )
        with pytest.raises(OAuthError) as exc:
            client.authorize_access_token(request)
        assert exc.value.description == 'Missing "request_token" in temporary data'


class TestOAuth2(base.BasePyTestCase):
    """Test OAuth2 authentication."""

    def test_oauth2_authorize(self):
        request = testing.DummyRequest(path="/login")
        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
        )
        rv = client.authorize_redirect(request, 'https://a.b/c')
        assert rv.status_code == 302
        url = rv.headers.get('location')
        assert 'state=' in url
        state = dict(url_decode(urlparse.urlparse(url).query))['state']

        with mock.patch('requests.sessions.Session.send') as send:
            send.return_value = mock_send_value(get_bearer_token())
            request2 = testing.DummyRequest(path='/authorize', params={"state": state})
            request2.session = request.session

            token = client.authorize_access_token(request2)
            assert token['access_token'] == 'a'

    def test_oauth2_authorize_access_denied(self):
        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
        )

        with mock.patch('requests.sessions.Session.send'):
            request = testing.DummyRequest(
                params={'error': 'access_denied', 'error_description': 'Not+Allowed'},
                path="/",
            )
            with pytest.raises(OAuthError):
                client.authorize_access_token(request)

    @pytest.mark.skipif(
        parse_version(authlib_version) < parse_version("1.0.0"),
        reason="Only on Authlib >= 1.0"
    )
    def test_oauth2_authorize_no_state(self):
        request = testing.DummyRequest(path="/login")
        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
        )
        with pytest.raises(RuntimeError):
            client.save_authorize_data(request, redirect_uri='https://a.b/c')

    def test_oauth2_authorize_code_challenge(self):
        request = testing.DummyRequest(path="/login")

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
            client_kwargs={'code_challenge_method': 'S256'},
        )
        rv = client.authorize_redirect(request, 'https://a.b/c')
        assert rv.status_code == 302
        url = rv.headers.get('location')
        assert 'state=' in url
        assert 'code_challenge=' in url

        state = dict(url_decode(urlparse.urlparse(url).query))['state']
        verifier = get_session_data(request.session, state, "code_verifier")

        def fake_send(sess, req, **kwargs):
            assert 'code_verifier={}'.format(verifier) in req.body
            return mock_send_value(get_bearer_token())

        with mock.patch('requests.sessions.Session.send', fake_send):
            request2 = testing.DummyRequest(
                path="/authorize",
                params={"state": state}
            )
            request2.session = request.session
            token = client.authorize_access_token(request2)
            assert token['access_token'] == 'a'

    def test_oauth2_authorize_code_verifier(self):
        request = testing.DummyRequest(path="/login")

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
            client_kwargs={'code_challenge_method': 'S256'},
        )
        state = 'foo'
        code_verifier = 'bar'
        rv = client.authorize_redirect(
            request, 'https://a.b/c',
            state=state, code_verifier=code_verifier
        )
        assert rv.status_code == 302
        url = rv.headers.get('location')
        assert 'state=' in url
        assert 'code_challenge=' in url

        with mock.patch('requests.sessions.Session.send') as send:
            send.return_value = mock_send_value(get_bearer_token())

            request2 = testing.DummyRequest(
                path='/authorize',
                params={"state": state},
            )
            request2.session = request.session

            token = client.authorize_access_token(request2)
            assert token['access_token'] == 'a'

    def test_openid_authorize(self):
        request = testing.DummyRequest(path="/login")
        key = jwk.dumps('secret', 'oct', kid='f')

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            jwks={'keys': [key]},
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
            client_kwargs={'scope': 'openid profile'},
        )

        resp = client.authorize_redirect(request, 'https://b.com/bar')
        assert resp.status_code == 302
        url = resp.headers.get('location')
        assert 'nonce=' in url

        query_data = dict(url_decode(urlparse.urlparse(url).query))
        token = get_bearer_token()
        token['id_token'] = generate_id_token(
            token, {'sub': '123'}, key,
            alg='HS256', iss='https://i.b',
            aud='dev', exp=3600, nonce=query_data['nonce'],
        )
        state = query_data['state']
        metadata = {
            "issuer": "https://i.b",
            "id_token_signing_alg_values_supported": ["HS256", "RS256"],
            'jwks': {'keys': [{'k': 'c2VjcmV0', 'kid': 'f', 'kty': 'oct'}]}
        }

        with (
            mock.patch('requests.sessions.Session.send') as send,
            mock.patch.object(client, "load_server_metadata") as load_server_metadata
        ):
            send.return_value = mock_send_value(token)
            load_server_metadata.return_value = metadata

            request2 = testing.DummyRequest(
                path='/authorize',
                params={"state": state, "code": 'foo'},
            )
            request2.session = request.session

            token = client.authorize_access_token(request2)
            assert token['access_token'] == 'a'
            assert 'userinfo' in token
            assert token['userinfo']['sub'] == '123'

    def test_oauth2_access_token_with_post(self):
        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
        )
        payload = {'code': 'a', 'state': 'b'}

        with mock.patch('requests.sessions.Session.send') as send:
            send.return_value = mock_send_value(get_bearer_token())
            request = testing.DummyRequest(path='/token', post=payload)
            set_session_data(request.session, "b", "state", "b")

            token = client.authorize_access_token(request)
            assert token['access_token'] == 'a'

    def test_with_fetch_token_in_oauth(self):
        def fetch_token(name, request):
            return {'access_token': name, 'token_type': 'bearer'}

        oauth = OAuth(fetch_token=fetch_token)
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize'
        )

        def fake_send(sess, req, **kwargs):
            if req.url.endswith(".well-known/openid-configuration"):
                return mock_send_value({})
            assert sess.token is not None
            assert sess.token['access_token'] == 'dev'
            return mock_send_value(get_bearer_token())

        with mock.patch('requests.sessions.Session.send', fake_send):
            request = testing.DummyRequest(path='/login')
            client.get('/user', request=request)

    def test_with_fetch_token_in_register(self):
        def fetch_token(request):
            return {'access_token': 'dev', 'token_type': 'bearer'}

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
            fetch_token=fetch_token,
        )

        def fake_send(sess, req, **kwargs):
            if req.url.endswith(".well-known/openid-configuration"):
                return mock_send_value({})
            assert sess.token is not None
            assert sess.token['access_token'] == 'dev'
            return mock_send_value(get_bearer_token())

        with mock.patch('requests.sessions.Session.send', fake_send):
            request = testing.DummyRequest(path='/login')
            client.get('/user', request=request)

    def test_request_without_token(self):
        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize'
        )

        def fake_send(sess, req, **kwargs):
            auth = req.headers.get('authorization')
            assert auth is None
            resp = mock.MagicMock()
            resp.text = 'hi'
            resp.status_code = 200
            return resp

        with mock.patch('requests.sessions.Session.send', fake_send):
            resp = client.get('/api/user', withhold_token=True)
            assert resp.text == 'hi'
            with pytest.raises(OAuthError):
                client.get('https://i.b/api/user')

    def test_update_token(self):

        old_token = dict(
            access_token='a', refresh_token='b',
            token_type='bearer', expires_at=100
        )

        def fetch_token(request):
            return old_token

        oauth = OAuth()
        client = oauth.register(
            'dev',
            client_id='dev',
            client_secret='dev',
            api_base_url='https://i.b/api',
            access_token_url='https://i.b/token',
            authorize_url='https://i.b/authorize',
            fetch_token=fetch_token,
        )

        new_token = get_bearer_token()

        def fake_send(sess, req, **kwargs):
            if req.url.endswith(".well-known/openid-configuration"):
                return mock_send_value({})
            if req.url == "https://i.b/token":
                return mock_send_value(new_token)
            if req.url == "https://i.b/user":
                return mock_send_value({})
            raise RuntimeError(req.url)

        listener = mock.Mock()
        self.config.add_subscriber(listener, TokenUpdate)

        with mock.patch('requests.sessions.Session.send', fake_send):
            request = testing.DummyRequest(path='/user')
            client.get('/user', request=request)

        assert listener.called
        event = listener.call_args[0][0]
        assert event.name == "dev"
        assert event.token == new_token
        assert event.refresh_token == "b"
