"""A Fedora-specific integration of Pyramid with Authlib.

This could be part of python-fedora for other pyramid-based apps
(except there aren't any at the moment).
"""

import time

from authlib import __version__ as authlib_version
from authlib.oauth2.rfc6750 import (
    BearerTokenValidator,
    InsufficientScopeError,
    InvalidTokenError,
)
from authlib.oauth2.rfc7662 import IntrospectionToken as BaseIntrospectionToken
from packaging.version import parse as parse_version
import requests


if parse_version(authlib_version) >= parse_version("1.0.0"):
    from .oauth_1 import PyramidOAuth2App as PyramidApp
else:
    from .oauth_015 import PyramidRemoteApp as PyramidApp


class IntrospectionToken(BaseIntrospectionToken):
    """An introspection token that implements is_expired() and is_revoked()."""

    def is_active(self):
        """Return whether the token is active."""
        return self['active']

    def is_expired(self):
        """Return whether the token is expired."""
        if not self.is_active():
            return True
        expires_at = self.get_expires_at()
        if not expires_at:
            return None
        return int(expires_at) < time.time()

    def is_revoked(self):
        """Return whether the token is revoked."""
        return not self.is_active()


class FedoraApp(PyramidApp):
    """Fedora-specific implementation of an Authlib app.

    This class adds support for some of Ipsilon's features.
    """

    def introspect_token(self, token_string):
        """Introspect the token by calling the OpenIDC provider.

        Args:
            token_string (str): The token

        Returns:
            IntrospectionToken: The result of the token introspection.
        """
        post_data = {
            'token': token_string,
            'token_type_hint': 'access_token',
            'client_id': self.client_id,
            "client_secret": self.client_secret
        }
        if self.access_token_url:
            access_token_url = self.access_token_url
        else:
            self.load_server_metadata()
            access_token_url = self.server_metadata["token_endpoint"]
        introspect_token_url = f"{access_token_url}Info"
        resp = requests.post(introspect_token_url, data=post_data)
        resp.raise_for_status()
        token_status = resp.json()
        # Add back the token itself because we'll need it later.
        token_status["access_token"] = token_string
        return IntrospectionToken(token_status)


class IntrospectTokenValidator(BearerTokenValidator):
    """Validates a token using introspection."""

    def __init__(self, app, *args, **kwargs):
        """Initialize the IntrospectTokenValidator."""
        super().__init__(*args, **kwargs)
        self.app = app

    def introspect_token(self, token_string):
        """Return the result of the app's introspection method."""
        return self.app.introspect_token(token_string)

    def authenticate_token(self, token_string):
        """Authenticate the token string and return an introspection result."""
        return self.introspect_token(token_string)

    def scope_insufficient(self, token, required_scopes):
        """Wrap the original method to support both Authlib < 1.0 and Authlib >= 1.0.

        Remove this when we only support Authlib >= 1.0.

        Args:
            token (IntrospectionToken): The token to check for insufficient scopes.
            required_scopes (list(str)): The list of required scopes.

        Returns:
            bool: Whether the token's scopes are sufficient.
        """
        if parse_version(authlib_version) >= parse_version("1.0.0"):
            return BearerTokenValidator.scope_insufficient(token.get_scope(), required_scopes)
        return super().scope_insufficient(token, required_scopes)

    def __call__(self, token_string, scopes, request, scope_operator="AND"):
        """Validate the token using introspection.

        Args:
            token_string (str): The token string.
            scopes (list): The list of required scopes.
            request (pyramid.request.Request): The Pyramid request
            scope_operator (str, optional): The operator between scopes. Defaults to "AND".

        Raises:
            InvalidTokenError: The token is invalid.
            InsufficientScopeError: The token does not have the required scopes.

        Returns:
            IntrospectedToken: The result of the token's introspection.
        """
        token = self.authenticate_token(token_string)
        self.validate_token(token, scopes, request)
        return token

    # In Authlib 1.0
    def validate_token(self, token, scopes, request):
        """Validate the token using introspection.

        Args:
            token_string (str): The token string.
            scopes (list): The list of required scopes.
            request (pyramid.request.Request): The Pyramid request
            scope_operator (str, optional): The operator between scopes. Defaults to "AND".

        Raises:
            InvalidTokenError: The token is invalid.
            InsufficientScopeError: The token does not have the required scopes.

        Returns:
            IntrospectedToken: The result of the token's introspection.
        """
        if not token:
            raise InvalidTokenError(realm=self.realm)
        if token.is_expired() or token.is_revoked():
            raise InvalidTokenError(realm=self.realm)
        if parse_version(authlib_version) < parse_version("1.0.0"):
            scopes = scopes[0]
        if self.scope_insufficient(token, scopes):
            if (
                parse_version(authlib_version) >= parse_version("0.15.5")
                and parse_version(authlib_version) < parse_version("1.0.0")
            ):
                raise InsufficientScopeError(
                    token_scope=token["scope"], required_scope=scopes
                )
            raise InsufficientScopeError()
