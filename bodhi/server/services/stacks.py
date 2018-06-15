# -*- coding: utf-8 -*-
# Copyright © 2014-2018 Red Hat, Inc.
#
# This file is part of Bodhi.
#
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
"""Define web services that pertain to Stacks."""

import math

from cornice import Service
from cornice.validators import colander_body_validator, colander_querystring_validator
from pyramid.exceptions import HTTPForbidden
from pyramid.view import view_config
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_

from bodhi.server import log, notifications, security
from bodhi.server.config import config
from bodhi.server.models import Package, Stack, Group, User
from bodhi.server.util import tokenize
from bodhi.server.validators import (validate_packages,
                                     validate_stack, validate_requirements)
import bodhi.server.schemas
import bodhi.server.services.errors


stack = Service(name='stack', path='/stacks/{name}',
                factory=security.PackagerACLFactory,
                validators=(validate_stack,),
                description='Bodhi Stacks',
                # Note, this 'rw' is not a typo.  there are deletes and posts.
                cors_origins=bodhi.server.security.cors_origins_rw)
stacks = Service(name='stacks', path='/stacks/',
                 description='Bodhi Stacks',
                 factory=security.PackagerACLFactory,
                 # Not a typo.  there are deletes and posts in here.
                 cors_origins=bodhi.server.security.cors_origins_rw)


@stack.get(accept="text/html", renderer="new_stack.html",
           error_handler=bodhi.server.services.errors.html_handler)
@stack.get(accept=('application/json', 'text/json'), renderer='json',
           error_handler=bodhi.server.services.errors.json_handler)
@stack.get(accept=('application/javascript'), renderer='jsonp',
           error_handler=bodhi.server.services.errors.jsonp_handler)
def get_stack(request):
    """
    Return a single Stack from its name.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: A dictionary with key "stack" that indexes the matched Stack.
    """
    return dict(stack=request.validated['stack'])


@stacks.get(accept="text/html", renderer='stacks.html',
            error_handler=bodhi.server.services.errors.html_handler,
            schema=bodhi.server.schemas.ListStackSchema,
            validators=(colander_querystring_validator, validate_packages,))
@stacks.get(accept=('application/json', 'text/json'),
            error_handler=bodhi.server.services.errors.json_handler,
            schema=bodhi.server.schemas.ListStackSchema,
            validators=(colander_querystring_validator, validate_packages,), renderer='json')
def query_stacks(request):
    """
    Return a paginated list of filtered stacks.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: A dictionary with the following keys: "stacks" indexing a list of Stacks that match
            the query, "page" indexing the current page, "pages" indexing the total number of pages,
            "rows_per_page" indexing how many rows are in a page, and "total" indexing the total
            number of matched Stacks.
    """
    data = request.validated
    query = request.db.query(Stack).order_by(Stack.name.desc())

    name = data.get('name')
    if name:
        query = query.filter_by(name=name)

    like = data.get('like')
    if like:
        query = query.filter(Stack.name.like('%%%s%%' % like))

    packages = data.get('packages')
    if packages:
        query = query.join(Package.stack)
        query = query.filter(or_(*[Package.name == pkg.name for pkg in packages]))

    # We can't use ``query.count()`` here because it is naive with respect to
    # all the joins that we're doing above.
    count_query = query.with_labels().statement\
        .with_only_columns([func.count(distinct(Stack.id))])\
        .order_by(None)
    total = request.db.execute(count_query).scalar()

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


@stacks.post(schema=bodhi.server.schemas.SaveStackSchema,
             permission='edit',
             validators=(colander_body_validator, validate_requirements,), renderer='json',
             error_handler=bodhi.server.services.errors.json_handler)
def save_stack(request):
    """
    Save a stack.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: A dictionary with key "stack" that indexes the newly created Stack.
    """
    data = request.validated
    db = request.db
    user = User.get(request.user.name)

    # Fetch or create the stack
    stack = Stack.get(data['name'])
    if not stack:
        stack = Stack(name=data['name'], users=[user])
        db.add(stack)
        db.flush()

    if stack.users or stack.groups:
        if user in stack.users:
            log.info('%s is an owner of the %s', user.name, stack.name)
        else:
            for group in user.groups:
                if group in stack.groups:
                    log.info('%s is a member of the %s group', user.name, stack.name)
                    break
            else:
                log.warning('%s is not an owner of the %s stack',
                            user.name, stack.name)
                log.debug('owners = %s; groups = %s', stack.users, stack.groups)
                request.errors.add('body', 'name', '%s does not have privileges'
                                   ' to modify the %s stack' % (user.name, stack.name))
                request.errors.status = HTTPForbidden.code
                return

    # Update the stack description
    desc = data['description']
    if desc:
        stack.description = desc

    # Update the stack requirements
    # If the user passed in no value at all for requirements, then use
    # the site defaults.  If, however, the user passed in the empty string, we
    # assume they mean *really*, no requirements so we leave the value null.
    reqs = data['requirements']
    if reqs is None:
        stack.requirements = config.get('site_requirements')
    elif reqs:
        stack.requirements = reqs

    stack.update_relationship('users', User, data, db)
    stack.update_relationship('groups', Group, data, db)

    # We make a special case out of packages here, since when a package is
    # added to a stack, we want to give it the same requirements as the stack
    # has. See https://github.com/fedora-infra/bodhi/issues/101
    new, same, rem = stack.update_relationship('packages', Package, data, db)
    if stack.requirements:
        additional = list(tokenize(stack.requirements))

        for name in new:
            package = Package.get(name)
            original = package.requirements
            original = [] if not original else list(tokenize(original))
            package.requirements = " ".join(list(set(original + additional)))

    log.info('Saved %s stack', data['name'])
    notifications.publish(topic='stack.save', msg=dict(
        stack=stack, agent=user.name))

    return dict(stack=stack)


@stack.delete(permission='edit', renderer='json',
              error_handler=bodhi.server.services.errors.json_handler)
def delete_stack(request):
    """
    Delete a stack.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: The dictionary {'status': 'success'}.
    """
    stack = request.validated['stack']
    notifications.publish(topic='stack.delete', msg=dict(
        stack=stack, agent=request.user.name))
    request.db.delete(stack)
    log.info('Deleted stack: %s', stack.name)
    return dict(status=u'success')


@view_config(route_name='new_stack', renderer='new_stack.html')
def new_stack(request):
    """
    Return the new stack form.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: An empty dictionary.
    Raises:
        pyramid.exceptions.HTTPForbidden: If the user is not logged in.
    """
    user = request.authenticated_userid
    if not user:
        raise HTTPForbidden("You must be logged in.")
    return dict()
