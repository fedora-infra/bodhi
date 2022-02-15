from unittest import mock

from authlib import __version__ as authlib_version
from authlib.oauth2.rfc6750 import InsufficientScopeError, InvalidTokenError
from pyramid import testing
import pkg_resources
import pytest

from bodhi.server.auth.fedora import FedoraRemoteApp, IntrospectTokenValidator
from bodhi.server.auth.oauth import OAuth

from .. import base
from ..utils import mock_send_value


SERVER_METADATA = {
    "token_endpoint": 'https://i.b/Token',
}
INTROSPECTION_RESULT = {
    "active": True,
    "client_id": "test-client-id",
    "username": "testuser",
    "scope": "read write dolphin",
    "sub": "Z5O3upPC88QrAjx00dis",
    "aud": "https://protected.example.net/resource",
    "iss": "https://server.example.com/",
    "exp": 1419356238,
    "iat": 1419350238
}


def make_fake_send(introspection_result=None):
    """Build a mock for requests.Session.send"""
    _introspection_result = INTROSPECTION_RESULT.copy()
    _introspection_result.update(introspection_result or {})

    def fake_send(sess, req, **kwargs):
        if req.url.endswith(".well-known/openid-configuration"):
            return mock_send_value(SERVER_METADATA)
        if req.url.endswith("/TokenInfo"):
            return mock_send_value(_introspection_result)
        raise ValueError(req.url)
    return fake_send


class TestFedoraAuth(base.BasePyTestCase):
    """Test the Fedora-specific authentication and ticket validation methods."""

    def setup_method(self, method):
        super().setup_method(method)
        oauth = OAuth()
        self.client = oauth.register(
            "dev",
            client_id="test-client-id",
            client_secret="test-client-secret",
            server_metadata_url=self.registry.settings["oidc.fedora.server_metadata_url"],
            client_kwargs={
                'scope': "openid email profile",
                'token_endpoint_auth_method': 'client_secret_post',
            },
            client_cls=FedoraRemoteApp,
        )

    def test_introspect_token(self):
        with mock.patch('requests.sessions.Session.send', make_fake_send()):
            token = self.client.introspect_token("TOKEN")
        # We're adding the active token in the dict, check it and then compare
        assert token.pop("access_token") == "TOKEN"
        assert token == INTROSPECTION_RESULT

    def test_introspect_token_with_access_token_url(self):
        self.client.access_token_url = "https://i.b/Token"
        with mock.patch('requests.sessions.Session.send', make_fake_send()):
            token = self.client.introspect_token("TOKEN")
        assert token["access_token"] == "TOKEN"

    def test_introspect_token_validator(self):
        validator = IntrospectTokenValidator(self.client)
        with mock.patch('requests.sessions.Session.send', make_fake_send()):
            token = validator("TOKEN", scopes=["read", "write"], request=testing.DummyRequest())
        assert token.pop("access_token") == "TOKEN"
        assert token == INTROSPECTION_RESULT

    def test_introspect_token_validator_invalid(self):
        validator = IntrospectTokenValidator(self.client)
        answer = {
            "active": False,
        }
        with mock.patch('requests.sessions.Session.send', make_fake_send(answer)):
            with pytest.raises(InvalidTokenError):
                validator("TOKEN", scopes=["read", "write"], request=testing.DummyRequest())

    def test_introspect_token_insufficient_scopes(self):
        validator = IntrospectTokenValidator(self.client)
        with mock.patch('requests.sessions.Session.send', make_fake_send({"scope": "read"})):
            with pytest.raises(InsufficientScopeError) as exc:
                validator("TOKEN", scopes=["read", "write"], request=testing.DummyRequest())
            if pkg_resources.safe_version(authlib_version) >= pkg_resources.safe_version("0.15.5"):
                assert exc.value.token_scope == "read"
                assert exc.value.required_scope == "read write"
