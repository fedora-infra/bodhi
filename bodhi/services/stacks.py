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

import math

from datetime import datetime, timedelta
from cornice import Service
from pyramid.view import view_config
from pyramid.exceptions import HTTPNotFound, HTTPForbidden
from pyramid.security import authenticated_userid
from sqlalchemy.sql import or_
from sqlalchemy import func

from bodhi import log
from bodhi.models import Update, Build, Package, Release, Stack
import bodhi.schemas
import bodhi.security
from bodhi.validators import (
    validate_nvrs,
    validate_version,
    validate_uniqueness,
    validate_tags,
    validate_acls,
    validate_builds,
    validate_enums,
    validate_updates,
    validate_packages,
    validate_stack,
    validate_release,
    validate_username,
    validate_groups,
)


stack = Service(name='stack', path='/stacks/{name}',
                validators=(validate_stack,),
                description='Bodhi Stacks')
stacks = Service(name='stacks', path='/stacks/',
                 description='Bodhi Stacks')


@stack.get(accept="text/html", renderer="new_stack.html")
@stack.get(accept=('application/json', 'text/json'), renderer='json')
@stack.get(accept=('application/javascript'), renderer='jsonp')
def get_stack(request):
    """Return a single Stack from its name"""
    return dict(stack=request.validated['stack'])


@stacks.get(accept="text/html", renderer='stacks.html',
            schema=bodhi.schemas.ListStackSchema,
            validators=(validate_packages,))
@stacks.get(accept=('application/json', 'text/json'),
            schema=bodhi.schemas.ListStackSchema,
            validators=(validate_packages,), renderer='json')
def query_stacks(request):
    """Return a paginated list of stacks"""
    data = request.validated
    query = request.db.query(Stack, func.count(Package.id))\
            .outerjoin(Package).group_by(Stack.id)\
            .order_by(func.count(Package.id).desc())

    name = data.get('name')
    if name:
        query = query.filter_by(name=name)

    like = data.get('like')
    if like:
        query = query.filter(Stack.name.like('%%%s%%' % like))

    packages = data.get('packages')
    if packages:
        query = query.join(Package.stack)
        query = query.filter(or_(*[Package.name==pkg.name for pkg in packages]))

    total = query.count()
    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        stacks=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
    )


@stacks.post(schema=bodhi.schemas.SaveStackSchema,
             acl=bodhi.security.packagers_allowed_acl,
             renderer='json')
def save_stack(request):
    """Save a stack"""
    data = request.validated
    db = request.db

    stack = Stack.get(data['name'], db)
    if not stack:
        stack = Stack(name=data['name'])
        db.add(stack)
        db.flush()

    desc = data['description']
    if desc:
        stack.description = desc

    packages = data['packages']
    if packages:
        for package in packages:
            pkg = Package.get(package, db)
            # FIXME: validate that this package exists from koji?
            if not pkg:
                pkg = Package(name=package)
                db.add(pkg)
                db.flush()
            if pkg not in stack.packages:
                stack.packages.append(pkg)

        # Remove packages that were unchecked
        for package in stack.packages:
            if package.name not in packages:
                log.info('Removing %s from %s stack', package.name, stack.name)
                stack.packages.remove(package)

    log.info('Saved %s stack', data['name'])

    return dict(stack=stack)


@stack.delete(acl=bodhi.security.packagers_allowed_acl, renderer='json')
def delete_stack(request):
    """Delete a stack"""
    stack = request.validated['stack']
    request.db.delete(stack)
    log.info('Deleted stack: %s', stack.name)
    return dict(status=u'success')


@view_config(route_name='new_stack', renderer='new_stack.html')
def new_stack(request):
    """ Returns the new stack form """
    user = authenticated_userid(request)
    if not user:
        raise HTTPForbidden("You must be logged in.")
    return dict()
