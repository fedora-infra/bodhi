"""Some authentication-related utilities."""

import typing

from pyramid.httpexceptions import HTTPFound, HTTPUnauthorized
from pyramid.security import remember

from bodhi.server import log
from bodhi.server.models import Group, User


if typing.TYPE_CHECKING:  # pragma: no cover
    import mako.runtime.Context  # noqa: 401
    import pyramid.request.Request  # noqa: 401
    import pyramid.response.Response  # noqa: 401


def get_and_store_user(
    request: 'pyramid.request.Request',
    access_token: str,
    response: 'pyramid.response.Response'
):
    """Get or create the user and log them in.

    Get additional information about the user from the OIDC provider, create it
    if it doesn't exist yet, sync the groups, and log them in.

    Args:
        request (pyramid.request.Request): The Pyramid request.
        access_token (str): A valid access token.
        response (pyramid.response.Response): The Pyramid response to add the session
            cookie headers to.

    Returns:
        bodhi.models.User: The user instance.
    """
    # Get information about the user
    userinfo = request.registry.oidc.fedora.userinfo(token={"access_token": access_token})
    username = userinfo['nickname']
    log.info(f'{username} successfully logged in')
    # Create or update the user in the database, update the groups
    user = create_or_update_user(
        request.db,
        username,
        userinfo['email'],
        userinfo.get("groups", []),
    )
    # Log the user in
    headers = remember(request, username)
    response.headerlist.extend(headers)
    return user


def remember_me(context: 'mako.runtime.Context', request: 'pyramid.request.Request',
                info: dict, *args, **kw) -> HTTPFound:
    """
    Remember information about a newly logged in user given by the OpenID provider.

    This is configured via the openid.success_callback configuration, and is called upon successful
    login.

    Args:
        context: The current template rendering context. Unused.
        request: The current request.
        info: The information passed to Bodhi from the OpenID provider about the
            authenticated user. This includes things like the user's username, e-mail address and
            groups.
        args: A list of additional positional parameters. Unused.
        kw: A dictionary of additional keyword parameters. Unused.
    Returns:
        A 302 redirect to the URL the user was visiting before
            they clicked login, or home if they have not used a valid OpenID provider.
    """
    log.debug('remember_me(%s)' % locals())
    log.debug('remember_me: request.params = %r' % request.params)
    endpoint = request.params['openid.op_endpoint']
    if endpoint != request.registry.settings['openid.provider']:
        log.warning('Invalid OpenID provider: %s' % endpoint)
        raise HTTPUnauthorized(
            'Invalid OpenID provider. You can only use: %s' %
            request.registry.settings['openid.provider']
        )

    username = info['sreg']['nickname']
    email = info['sreg']['email']
    log.debug('remember_me: groups = %s' % info['groups'])
    log.info('%s successfully logged in' % username)

    create_or_update_user(request.db, username, email, info["groups"])

    headers = remember(request, username)

    response = get_final_redirect(request)
    response.headerlist.extend(headers)
    return response


def create_or_update_user(db, username, email, groups):
    """Create or update a user in the database.

    Args:
        db (sqlalchemy.orm.session.Session): The database session.
        username (str): The username to create or update
        email (str): The user's email address
        groups (list(str)): A list of group names the user belongs to, that will be synced.

    Returns:
        bodhi.server.models.User: The user instance.
    """
    # Find the user in our database. Create it if it doesn't exist.
    user = db.query(User).filter_by(name=username).first()
    if not user:
        user = User(name=username, email=email)
        db.add(user)
        db.flush()
    else:
        # Update email address if the address changed
        if user.email != email:
            user.email = email
            db.flush()

    # Keep track of what groups the user is a member of
    for group_name in groups:
        # Drop empty group names https://github.com/fedora-infra/bodhi/issues/306
        if not group_name.strip():
            continue

        group = db.query(Group).filter_by(name=group_name).first()
        if not group:
            group = Group(name=group_name)
            db.add(group)
            db.flush()
        if group not in user.groups:
            log.info('Adding %s to %s group', user.name, group.name)
            user.groups.append(group)

    # See if the user was removed from any groups
    for group in user.groups:
        if group.name not in groups:
            log.info('Removing %s from %s group', user.name, group.name)
            user.groups.remove(group)

    return user


def get_final_redirect(request: 'pyramid.request.Request'):
    """Get the URL that the user should be redirected to after logging in.

    Args:
        request (pyramid.request.Request): the current request.

    Returns:
        HTTPFound: An HTTP 302 response redirecting to the right URL.
    """
    came_from = request.session.get('came_from', request.route_path("home"))
    request.session.pop('came_from', None)

    # Mitigate "Covert Redirect"
    if not came_from.startswith(request.host_url):
        came_from = request.route_path("home")
    # Don't redirect endlessly to the login view
    if came_from.startswith(request.route_url('login')):
        came_from = request.route_path("home")

    return HTTPFound(location=came_from)
