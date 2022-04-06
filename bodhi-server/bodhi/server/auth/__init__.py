"""This module sets up OpenID Connect authentication for Bodhi."""

from authlib import __version__ as authlib_version
from packaging.version import parse as parse_version

from .constants import SCOPES
from .fedora import FedoraApp


if parse_version(authlib_version) >= parse_version("1.0.0"):
    from .oauth_1 import OAuth
else:
    from .oauth_015 import OAuth


def includeme(config):
    """Set up the authentication."""
    # OpenID
    config.add_route('login', '/login')
    config.add_view('bodhi.server.auth.views.login', route_name='login')
    config.add_route('logout', '/logout')
    config.add_view('bodhi.server.auth.views.logout', route_name='logout')
    config.add_route('verify_openid', pattern='/dologin.html')
    config.add_view('pyramid_fas_openid.verify_openid', route_name='verify_openid')

    # OIDC (OpenID Connect)
    oauth = OAuth()
    oauth.register(
        "fedora",
        client_kwargs={
            'scope': SCOPES,
            'token_endpoint_auth_method': 'client_secret_post',
        },
        client_cls=FedoraApp,
    )
    config.registry.oidc = oauth

    config.add_route('oidc_login', '/oidc/login')
    config.add_view('bodhi.server.auth.views.login_oidc', route_name='oidc_login')
    config.add_route('oidc_authorize', '/oidc/authorize')
    config.add_view('bodhi.server.auth.views.authorize_oidc', route_name='oidc_authorize')
    config.add_route('oidc_login_with_token', '/oidc/login-token')
    config.add_view('bodhi.server.auth.views.login_with_token', route_name='oidc_login_with_token')
