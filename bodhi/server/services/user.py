# Copyright 2014-2019 Red Hat, Inc. and others
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
"""Defines API services that pertain to users."""
import math

from cornice import Service
from cornice.validators import colander_querystring_validator
from pyramid.exceptions import HTTPNotFound
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_

from bodhi.server.models import Group, Update, User
from bodhi.server.validators import (validate_updates, validate_groups)
import bodhi.server.schemas
import bodhi.server.security
import bodhi.server.services.errors
import bodhi.server.services.updates


user = Service(name='user', path='/users/{name}',
               description='Bodhi users',
               # These we leave wide-open since these are only GETs
               cors_origins=bodhi.server.security.cors_origins_ro)

users = Service(name='users', path='/users/',
                description='Bodhi users',
                # These we leave wide-open since these are only GETs
                cors_origins=bodhi.server.security.cors_origins_ro)

users_rss = Service(name='users_rss', path='/rss/users/', description='Bodhi users RSS feed',
                    cors_origins=bodhi.server.security.cors_origins_ro)


@user.get(accept=("application/json", "text/json"), renderer="json",
          error_handler=bodhi.server.services.errors.json_handler)
@user.get(accept=("application/javascript"), renderer="jsonp",
          error_handler=bodhi.server.services.errors.json_handler)
@user.get(accept="text/html", renderer="user.html",
          error_handler=bodhi.server.services.errors.html_handler)
def get_user(request):
    """
    Return a user given by username.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary with two keys. "user" maps to a dictionary representation of the User
            object. "urls" maps to various URLs that describe various other objects related to the
            user.
    """
    id = request.matchdict.get('name')
    user = User.get(id)

    if not user:
        request.errors.add('body', 'name', 'No such user')
        request.errors.status = HTTPNotFound.code
        return

    user = user.__json__(request)

    # Throw some extra information in there
    rurl = request.route_url  # Just shorthand
    urls = {
        'comments_by': rurl('comments') + '?user=%s' % id,
        'comments_on': rurl('comments') + '?update_owner=%s' % id,
        'recent_updates': rurl('updates') + '?user=%s' % id,
        'recent_overrides': rurl('overrides') + '?user=%s' % id,
        'comments_by_rss': rurl('comments_rss') + '?user=%s' % id,
        'comments_on_rss': rurl('comments_rss') + '?update_owner=%s' % id,
        'recent_updates_rss': rurl('updates_rss') + '?user=%s' % id,
        'recent_overrides_rss': rurl('overrides_rss') + '?user=%s' % id,
    }

    return dict(user=user, urls=urls)


validators = (
    colander_querystring_validator,
    validate_groups,
    validate_updates,
)


@users.get(schema=bodhi.server.schemas.ListUserSchema,
           accept=("application/json", "text/json"), renderer="json",
           error_handler=bodhi.server.services.errors.json_handler,
           validators=validators)
@users.get(schema=bodhi.server.schemas.ListUserSchema,
           accept=("application/javascript"), renderer="jsonp",
           error_handler=bodhi.server.services.errors.jsonp_handler,
           validators=validators)
@users.get(schema=bodhi.server.schemas.ListUserSchema, renderer="rss",
           accept=('application/atom+xml',),
           error_handler=bodhi.server.services.errors.html_handler,
           validators=validators)
@users_rss.get(schema=bodhi.server.schemas.ListUserSchema, renderer="rss",
               error_handler=bodhi.server.services.errors.html_handler,
               validators=validators)
def query_users(request):
    """
    Search for users by various criteria.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: A dictionary with the follow key mappings:
            users: A list of users matching the search criteria.
            page: The current page of results.
            pages: The total number of pages available.
            rows_per_page: The number of users on the page.
            total: The total number of users matching the search criteria.
    """
    db = request.db
    data = request.validated
    query = db.query(User)

    like = data.get('like')
    if like is not None:
        query = query.filter(or_(*[
            User.name.like('%%%s%%' % like)
        ]))

    search = data.get('search')
    if search is not None:
        query = query.filter(User.name.ilike('%%%s%%' % search))

    name = data.get('name')
    if name is not None:
        query = query.filter(User.name.like(name))

    groups = data.get('groups')
    if groups is not None:
        query = query.join(User.groups)
        query = query.filter(or_(*[Group.id == grp.id for grp in groups]))

    updates = data.get('updates')
    if updates is not None:
        query = query.join(User.updates)
        args = [Update.alias == update.alias for update in updates]
        query = query.filter(or_(*args))

    # We can't use ``query.count()`` here because it is naive with respect to
    # all the joins that we're doing above.
    count_query = query.with_labels().statement\
        .with_only_columns([func.count(distinct(User.id))])\
        .order_by(None)
    total = request.db.execute(count_query).scalar()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        users=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
    )
