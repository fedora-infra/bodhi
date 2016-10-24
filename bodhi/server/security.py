# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from cornice.errors import Errors

from pyramid.security import (Allow, ALL_PERMISSIONS, DENY_ALL)
from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPFound
from pyramid.threadlocal import get_current_registry

from . import log
from .models import User, Group


#
# Pyramid ACL factories
#

def admin_only_acl(request):
    """Generate our admin-only ACL"""
    return [(Allow, 'group:' + group, ALL_PERMISSIONS) for group in
            request.registry.settings['admin_groups'].split()] + \
           [DENY_ALL]


def packagers_allowed_acl(request):
    """Generate an ACL for update submission"""
    groups = request.registry.settings['mandatory_packager_groups'].split()
    return [
        (Allow, 'group:' + group, ALL_PERMISSIONS) for group in groups
    ] + [DENY_ALL]


#
# OpenID views
#

def login(request):
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        referrer = request.route_url('home')
    came_from = request.params.get('came_from', referrer)
    request.session['came_from'] = came_from
    oid_url = request.registry.settings['openid.url']
    return HTTPFound(location=request.route_url('verify_openid',
                                                _query=dict(openid=oid_url)))


def logout(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


#
# openid.success_callback
#

def remember_me(context, request, info, *args, **kw):
    """ Called upon successful login """
    log.debug('remember_me(%s)' % locals())
    log.debug('remember_me: request.params = %r' % request.params)
    endpoint = request.params['openid.op_endpoint']
    if endpoint != request.registry.settings['openid.provider']:
        log.warn('Invalid OpenID provider: %s' % endpoint)
        request.session.flash('Invalid OpenID provider. You can only use: %s' %
                              request.registry.settings['openid.provider'])
        return HTTPFound(location=request.route_url('home'))

    username = unicode(info['identity_url'].split('http://')[1].split('.')[0])
    email = info['sreg']['email']
    log.debug('remember_me: groups = %s' % info['groups'])
    log.info('%s successfully logged in' % username)

    # Find the user in our database. Create it if it doesn't exist.
    db = request.db
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

    # Keep track of what groups the user is a memeber of
    for group_name in info['groups']:
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
        if group.name not in info['groups']:
            log.info('Removing %s from %s group', user.name, group.name)
            user.groups.remove(group)

    headers = remember(request, username)
    came_from = request.session['came_from']
    del(request.session['came_from'])

    # Mitigate "Covert Redirect"
    if not came_from.startswith(request.host_url):
        came_from = '/'

    response = HTTPFound(location=came_from)
    response.headerlist.extend(headers)
    return response


class CorsOrigins(object):
    """ Proxy-list class to load CORS config after scan-time.

    This should appear to behave just like a list, but it loads values from the
    pyramid configuration for its values.  AFAIK, we have to do things this way
    since Cornice expects its cors configuration to be present at import-time,
    but the configuration isn't available until later, at Pyramid scan-time.
    Luckily, Cornice doesn't iterate over that configuration until
    request-time, so we can load this then.

        >>> cors_origins_ro = CorsOrigins('cors_origins_ro')
        >>> cors_origins_ro[0]
        ['*']
        >>> cors_origins_rw = CorsOrigins('cors_origins_rw')
        >>> cors_origins_rw[0]
        ['bodhi.fedoraproject.org']

    """
    def __init__(self, name):
        self.name = name
        self.origins = None

    def initialize(self):
        if self.origins is None:
            settings = get_current_registry().settings
            self.origins = settings.get(self.name, 'localhost').split(',')

    def __len__(self):
        if self.origins is None:
            self.initialize()
        return len(self.origins)

    def __getitem__(self, key):
        if self.origins is None:
            self.initialize()
        return self.origins[key]

    def __iter__(self):
        if self.origins is None:
            self.initialize()
        return iter(self.originals)

    def __contains__(self, item):
        if self.origins is None:
            self.initialize()
        return item in self.originals


cors_origins_ro = CorsOrigins('cors_origins_ro')
cors_origins_rw = CorsOrigins('cors_origins_rw')


class ProtectedRequest(object):
    """ A proxy to the request object.

    The point here is that you can set 'errors' on this request, but they
    will be sent to /dev/null and hidden from cornice.  Otherwise, this
    object behaves just like a normal request object.
    """
    def __init__(self, real_request):
        # Hide errors added to this from the real request
        self.errors = Errors()
        # But proxy other attributes to the real request
        self.real_request = real_request
        for attr in ['db', 'registry', 'validated', 'buildinfo', 'user']:
            setattr(self, attr, getattr(self.real_request, attr))
