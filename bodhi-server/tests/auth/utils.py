"""Utility functions for the authentication unit tests."""

import time

from authlib import __version__ as authlib_version
from packaging.version import parse as parse_version

from bodhi.server.auth.constants import SCOPES

from ..utils import get_bearer_token, mock_send_value


def set_session_data(session, state, key, value, app_name="dev"):
    """Set the session data with any Authlib version."""
    if parse_version(authlib_version) < parse_version("1.0.0"):
        session[f"_{app_name}_authlib_{key}_"] = value
    else:
        session[f'_state_{app_name}_{state}'] = {"data": {key: value}}


def get_session_data(session, state, key, app_name="dev"):
    """Get the session data with any Authlib version."""
    if parse_version(authlib_version) < parse_version("1.0.0"):
        return session[f"_{app_name}_authlib_{key}_"]
    else:
        return session[f'_state_{app_name}_{state}']["data"][key]


def fake_send(responses=None):
    """Mock the OIDC provider's response."""
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
