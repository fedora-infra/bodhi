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

from pyramid.security import (Allow, Deny, Everyone, Authenticated,
                              ALL_PERMISSIONS, DENY_ALL)
from pyramid.security import remember, forget
from pyramid.httpexceptions import HTTPFound

from . import log
from .models import User, Group, Update


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
    log.debug('packagers_allowed_acl!!')
    return [(Allow, 'group:' + group, ALL_PERMISSIONS) for group in
            request.registry.settings['mandatory_packager_groups'].split()] + \
           [DENY_ALL]


def package_maintainers_only_acl(request):
    """An ACL that only allows package maintainers for a given package"""
    acl = admin_only_acl(request)
    update = Update.get(request.matchdict['id'], request.db)
    if update:
        for committer in update.get_maintainers():
            acl.insert(0, (Allow, committer, ALL_PERMISSIONS))
    return acl


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
    log.debug('request.params = %r' % request.params)
    endpoint = request.params['openid.op_endpoint']
    if endpoint != request.registry.settings['openid.provider']:
        log.warn('Invalid OpenID provider: %s' % endpoint)
        request.session.flash('Invalid OpenID provider. You can only use: %s' %
                              request.registry.settings['openid.provider'])
        return HTTPFound(location=request.route_url('home'))

    username = unicode(info['identity_url'].split('http://')[1].split('.')[0])
    log.info('%s successfully logged in' % username)
    log.debug('groups = %s' % info['groups'])

    # Find the user in our database. Create it if it doesn't exist.
    db = request.db
    user = db.query(User).filter_by(name=username).first()
    if not user:
        user = User(name=username)
        db.add(user)
        db.flush()

    # Keep track of what groups the user is a memeber of
    for group_name in info['groups']:
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
