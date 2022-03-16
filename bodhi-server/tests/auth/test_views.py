from unittest import mock
from urllib.parse import urlparse
import time

from authlib.common.urls import url_decode
from pyramid import testing
from pyramid.httpexceptions import HTTPUnauthorized
import pytest

from bodhi.server import models
from bodhi.server.auth.constants import SCOPES
from bodhi.server.auth.views import authorize_oidc, login_with_token

from .. import base
from ..utils import get_bearer_token, mock_send_value
from .utils import set_session_data


def fake_send(responses=None):
    now = int(time.time())
    default_responses = {
        "UserInfo": {
            "sub": "SUB",
            "nickname": "testuser",
            "email": "testuser@example.com",
            "groups": ["testgroup1", "testgroup2"]
        },
        "openid-configuration": {
            "userinfo_endpoint": "https://id.stg.fedoraproject.org/openidc/UserInfo",
            "token_endpoint": "https://id.stg.fedoraproject.org/openidc/Token",
            "authorization_endpoint": "https://id.stg.fedoraproject.org/openidc/Authorization",
        },
        "Token": get_bearer_token(),
        "TokenInfo": {
            "active": True,
            "client_id": "test-client-id",
            "username": "testuser",
            "scope": SCOPES,
            "sub": "SUB",
            "aud": "https://protected.example.net/resource",
            "iss": "https://server.example.com/",
            "exp": now + 3600,
            "iat": now
        },
    }
    _responses = default_responses.copy()
    _responses.update(responses or {})

    def _mocker(req, **kwargs):
        for endpoint, response in _responses.items():
            if req.url.endswith(f"/{endpoint}"):
                return mock_send_value(response)
        raise RuntimeError(f"Unsupported URL: {req.url}")
    return _mocker


class TestLogin(base.BasePyTestCase):
    """Test the login() function."""
    def test_login(self):
        """Test the login redirect"""
        resp = self.app.get('/login', status=302)
        assert resp.location == "http://localhost/oidc/login"

    def test_login_openid(self):
        """Test the login redirect for openid"""
        resp = self.app.get('/login?method=openid', status=302)
        assert 'dologin.html' in resp


class TestLogout(base.BasePyTestCase):
    """Test the logout() function."""
    def test_logout(self):
        """Test the logout redirect"""
        resp = self.app.get('/logout', status=302)
        assert resp.location in 'http://localhost/'


class TestOIDCLoginViews(base.BasePyTestCase):
    """Test the OIDC login views."""

    def test_login(self):
        """Test the login redirect"""
        self.registry.oidc.fedora.client_id = "test-client-id"
        with mock.patch('requests.sessions.Session.send', side_effect=fake_send()):
            resp = self.app.get('/oidc/login', status=302)
        location = urlparse(resp.location)
        assert location.scheme == "https"
        assert location.netloc == "id.stg.fedoraproject.org"
        assert location.path == "/openidc/Authorization"

        query_data = dict(url_decode(location.query))
        assert query_data["response_type"] == "code"
        assert query_data["client_id"] == "test-client-id"
        assert query_data["redirect_uri"] == "http://localhost/oidc/authorize"
        assert set(query_data["scope"].split(" ")) == set([
            'openid', 'email', 'profile',
            'https://id.fedoraproject.org/scope/groups',
            'https://id.fedoraproject.org/scope/agreements',
        ])

    def test_authorize(self):
        """Test a user logging in."""
        request = testing.DummyRequest(path="/oidc/authorize", params={"state": "STATE"})
        set_session_data(request.session, "STATE", "state", "STATE", app_name="fedora")
        request.registry = self.registry
        request.db = self.db

        with mock.patch('requests.sessions.Session.send', side_effect=fake_send()):
            response = authorize_oidc(request)

        assert response.status_code == 302
        assert response.location == "/"
        user = models.User.get('testuser')
        assert user.email == "testuser@example.com"
        assert [g.name for g in user.groups] == ["testgroup1", "testgroup2"]

    def test_authorize_update_email_groups(self):
        """Make sure the email and the groups are updated upon login."""
        user = models.User(name='testuser', email='testuser@example.com')
        self.db.add(user)
        self.db.flush()
        user.groups = [models.Group(name="testgroup1"), models.Group(name="testgroup2")]
        self.db.commit()

        request = testing.DummyRequest(path="/oidc/authorize", params={"state": "STATE"})
        set_session_data(request.session, "STATE", "state", "STATE", app_name="fedora")
        request.registry = self.registry
        request.db = self.db

        _fake_send = fake_send({
            "UserInfo": {
                "sub": "SUB",
                "nickname": "testuser",
                "email": "newaddress@example.com",
                "groups": ["testgroup1", "testgroup3"],
            }
        })

        with mock.patch('requests.sessions.Session.send', side_effect=_fake_send):
            response = authorize_oidc(request)

        assert response.status_code == 302
        user = models.User.get('testuser')
        assert user.email == "newaddress@example.com"
        assert [g.name for g in user.groups] == ["testgroup1", "testgroup3"]

    def test_authorize_error(self):
        """Test login failure handling."""
        request = testing.DummyRequest(
            path="/oidc/authorize",
            params={
                "state": "STATE",
                "error": "test_error",
                "error_description": "This is a test error"
            }
        )
        set_session_data(request.session, "STATE", "state", "STATE", app_name="fedora")
        request.registry = self.registry

        with mock.patch('requests.sessions.Session.send', side_effect=fake_send()):
            with pytest.raises(HTTPUnauthorized) as exc:
                authorize_oidc(request)
        assert exc.value.status_code == 401
        assert str(exc.value) == "Authentication failed: This is a test error"

    def test_login_with_token(self):
        """Test a user logging in with a token."""
        request = testing.DummyRequest(
            path="/oidc/login-with-token",
            headers={"Authorization": "Bearer TOKEN"}
        )
        request.registry = self.registry
        request.db = self.db

        with mock.patch('requests.sessions.Session.send', side_effect=fake_send()):
            response = login_with_token(request)

        assert response.status_code == 202
        user = models.User.get('testuser')
        assert user.email == "testuser@example.com"
        assert [g.name for g in user.groups] == ["testgroup1", "testgroup2"]
