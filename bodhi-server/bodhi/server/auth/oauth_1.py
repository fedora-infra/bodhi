"""This module contains generic Pyramid integration with Authlib >= 1.0.

It could be sent to Authlib upstream.
"""

from authlib.integrations.base_client import (
    BaseApp,
    BaseOAuth,
    FrameworkIntegration,
    OAuth1Mixin,
    OAuth2Mixin,
    OAuthError,
    OpenIDMixin,
)
from authlib.integrations.requests_client import OAuth1Session, OAuth2Session

from .oauth import PyramidAppMixin, PyramidIntegrationMixin


class PyramidIntegration(PyramidIntegrationMixin, FrameworkIntegration):
    """Pyramid-specific framework integration."""


class PyramidAppMixinAuthlib1(PyramidAppMixin):
    """Generic methods for a Pyramid Authlib app running on Authlib 1.x."""

    def save_authorize_data(self, request, **kwargs):
        """Save the authorization data in the session."""
        state = kwargs.pop('state', None)
        if state:
            self.framework.set_state_data(request.session, state, kwargs)
        else:
            raise RuntimeError('Missing state value')


class PyramidOAuth1App(PyramidAppMixinAuthlib1, OAuth1Mixin, BaseApp):
    """OAuth1 Authlib application for Pyramid."""

    client_cls = OAuth1Session

    def authorize_access_token(self, request, **kwargs):
        """Fetch access token in one step.

        :param request: HTTP request instance from Django view.
        :return: A token dict.
        """
        params = dict(request.GET)
        state = params.get('oauth_token')
        if not state:
            raise OAuthError(description='Missing "oauth_token" parameter')

        data = self.framework.get_state_data(request.session, state)
        if not data:
            raise OAuthError(description='Missing "request_token" in temporary data')

        params['request_token'] = data['request_token']
        params.update(kwargs)
        self.framework.clear_state_data(request.session, state)
        return self.fetch_access_token(**params)


class PyramidOAuth2App(PyramidAppMixinAuthlib1, OAuth2Mixin, OpenIDMixin, BaseApp):
    """OAuth2 Authlib application for Pyramid."""

    client_cls = OAuth2Session

    def authorize_access_token(self, request, **kwargs):
        """Fetch access token in one step.

        :param request: HTTP request instance from Pyramid view.
        :return: A token dict.
        """
        if request.method == 'GET':
            error = request.GET.get('error')
            if error:
                self.framework.clear_state_data(request.session, request.GET.get('state'))
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

        state_data = self.framework.get_state_data(request.session, params.get('state'))
        self.framework.clear_state_data(request.session, params.get('state'))
        params = self._format_state_params(state_data, params)
        token = self.fetch_access_token(**params, **kwargs)

        if 'id_token' in token and 'nonce' in state_data:
            userinfo = self.parse_id_token(token, nonce=state_data['nonce'])
            token['userinfo'] = userinfo
        return token


class OAuth(BaseOAuth):
    """A Pyramid-specific OAuth app."""

    oauth1_client_cls = PyramidOAuth1App
    oauth2_client_cls = PyramidOAuth2App
    framework_integration_cls = PyramidIntegration
