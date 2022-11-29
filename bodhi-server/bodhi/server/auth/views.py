"""Views related to authentication."""

import typing

from authlib.integrations.base_client import OAuthError
from authlib.oauth2 import ResourceProtector
from pyramid.httpexceptions import HTTPAccepted, HTTPFound, HTTPUnauthorized
from pyramid.security import forget

from bodhi.server import log

from .constants import SCOPES
from .fedora import IntrospectTokenValidator
from .utils import get_and_store_user, get_final_redirect


if typing.TYPE_CHECKING:  # pragma: no cover
    import pyramid.request.Request  # noqa: 401
    import pyramid.response.Response  # noqa: 401


def login(request: 'pyramid.request.Request') -> HTTPFound:
    """
    Redirect the user to the OpenID provider to perform a login.

    Args:
        request: The current request.
    Returns:
        A 302 redirect to the OpenID provider.
    """
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        referrer = request.route_url('home')
    came_from = request.params.get('came_from', referrer)
    request.session['came_from'] = came_from
    if request.GET.get("method", "oidc") == "openid":
        oid_url = request.registry.settings['openid.url']
        return HTTPFound(
            location=request.route_url(
                'verify_openid', _query=dict(openid=oid_url)
            )
        )
    # Use OIDC
    return HTTPFound(location=request.route_url('oidc_login'))


def logout(request: 'pyramid.request.Request') -> HTTPFound:
    """
    Log out the user.

    Args:
        request: The current request, which is used to remove the user's
            authentication cookies.
    Returns:
        A 302 redirect to the home page.
    """
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


def login_oidc(request: 'pyramid.request.Request'):
    """Send the user to the OpenID Connect provider to log in.

    Args:
        request (pyramid.request.Request): The Pyramid request.

    Returns:
        pyramid.response.Response: A redirect to the OIDC provider's login frame.
    """
    provider = request.registry.oidc.create_client('fedora')
    redirect_uri = request.route_url('oidc_authorize')
    return provider.authorize_redirect(request, redirect_uri)


def authorize_oidc(request: 'pyramid.request.Request'):
    """Verify the response from the OpenID Connect provider and log the user in.

    Args:
        request (pyramid.request.Request): The Pyramid request.

    Returns:
        pyramid.response.Response: A redirection to the previously visited page.
    """
    # After user confirmed on Fedora authorization page, it will redirect back to Bodhi to
    # authorize. In this route, we get the user's profile information, store the user
    # information in the database, mark the user as logged in, etc.
    try:
        token = request.registry.oidc.fedora.authorize_access_token(request)
    except OAuthError as e:
        log.warning(f"OIDC authorization failed: {e}")
        raise HTTPUnauthorized(f'Authentication failed: {e.description}')
    response = get_final_redirect(request)
    get_and_store_user(request, token["access_token"], response)
    return response


def login_with_token(request: 'pyramid.request.Request'):
    """Use a Bearer token to log in and get a Pyramid session ticket.

    Args:
        request (pyramid.request.Request): The Pyramid request

    Returns:
        pyramid.response.Response: An empty response if the login worked, but with the session
            cookie headers.
    """
    # Check the Bearer token and log the user in
    resource_protector = ResourceProtector()
    validator = IntrospectTokenValidator(request.registry.oidc.fedora)
    resource_protector.register_token_validator(validator)
    token = resource_protector.validate_request([SCOPES], request)
    response = HTTPAccepted()
    get_and_store_user(request, token["access_token"], response)
    return response
