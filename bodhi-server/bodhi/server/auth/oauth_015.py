"""This module contains generic Pyramid integration with Authlib < 1.0."""

from authlib.integrations.base_client import (
    BaseOAuth,
    FrameworkIntegration,
    OAuthError,
    RemoteApp,
)
from authlib.integrations.requests_client import OAuth1Session, OAuth2Session

from .oauth import PyramidAppMixin, PyramidIntegrationMixin


class PyramidIntegration(PyramidIntegrationMixin, FrameworkIntegration):
    """Pyramid framework integration."""

    oauth1_client_cls = OAuth1Session
    oauth2_client_cls = OAuth2Session
    expires_in = 3600

    def generate_access_token_params(self, request_token_url, request):
        """Generate parameters for fetching access token from the request.

        :param request_token_url: Request Token endpoint for OAuth 1
        :param request: The Pyramid request.

        :raise: OAuthError

        :return: The dict of the parameters for fetching access token.
        """
        if request_token_url:
            return dict(request.GET)

        if request.method == 'GET':
            error = request.GET.get('error')
            if error:
                description = request.GET.get('error_description')
                raise OAuthError(error=error, description=description)

            params = {
                'code': request.GET.get('code'),
                'state': request.GET.get('state'),
            }
        else:
            params = {
                'code': request.POST.get('code'),
                'state': request.POST.get('state'),
            }
        return params


class PyramidRemoteApp(PyramidAppMixin, RemoteApp):
    """Pyramid remote app."""

    def authorize_access_token(self, request, **kwargs):
        """Fetch access token in one step.

        :param request: HTTP request instance from Pyramid view.
        :return: A token dict.
        """
        params = self.retrieve_access_token_params(request)
        params.update(kwargs)
        token = self.fetch_access_token(**params)
        if 'id_token' in token:
            userinfo = self.parse_id_token(request, token)
            token['userinfo'] = userinfo
        return token

    def parse_id_token(self, request, token, claims_options=None, leeway=120):
        """Return an instance of UserInfo from token's ``id_token``.

        :param request: The Pyramid request.
        :param token: The token to parse.
        :param claims_options: Claims options for ``jwt.decode()``.
        :param leeway: The leeway to validate the claims. Defaults to 120.

        :return: ``UserInfo``
        """
        return self._parse_id_token(request, token, claims_options, leeway)


class OAuth(BaseOAuth):
    """Pyramid-specific OAuth app."""

    framework_client_cls = PyramidRemoteApp
    framework_integration_cls = PyramidIntegration
