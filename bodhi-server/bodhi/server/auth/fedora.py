"""A Fedora-specific integration of Pyramid with Authlib.

This could be part of python-fedora for other pyramid-based apps
(except there aren't any at the moment).
"""

from authlib import __version__ as authlib_version
from authlib.oauth2.rfc6750 import (
    BearerTokenValidator,
    InsufficientScopeError,
    InvalidTokenError,
)
from authlib.oauth2.rfc7662 import IntrospectionToken
import pkg_resources
import requests

from .oauth import PyramidRemoteApp


class FedoraRemoteApp(PyramidRemoteApp):
    """Fedora-specific implementation of an Authlib remote app.

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
        if not token or not token['active']:
            raise InvalidTokenError(realm=self.realm)
        if self.scope_insufficient(token, scopes, scope_operator):
            # Coverage: we don't have a good way to handle coverage when it's version-dependant.
            # Maybe with https://pypi.org/project/coverage-conditional-plugin/ ?
            # For now exclude both cases from coverage check.
            if pkg_resources.safe_version(authlib_version) < pkg_resources.safe_version("0.15.5"):
                raise InsufficientScopeError()  # pragma: no cover
            else:
                raise InsufficientScopeError(
                    token_scope=token["scope"], required_scope=" ".join(scopes)
                )  # pragma: no cover
        return token
