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

from cornice import Service
from pyramid.exceptions import HTTPNotFound
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_

from bodhi.server.models import Group, RpmPackage, Update, User
from bodhi.server.validators import validate_updates, validate_packages, validate_groups
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
    id = request.matchdict.get('name')
    user = User.get(id, request.db)

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
    validate_groups,
    validate_updates,
    validate_packages,
)


@users.get(schema=bodhi.server.schemas.ListUserSchema,
           accept=("application/json", "text/json"), renderer="json",
           error_handler=bodhi.server.services.errors.json_handler,
           validators=validators)
@users.get(schema=bodhi.server.schemas.ListUserSchema,
           accept=("application/javascript"), renderer="jsonp",
           error_handler=bodhi.server.services.errors.jsonp_handler,
           validators=validators)
@users_rss.get(schema=bodhi.server.schemas.ListUserSchema, renderer="rss",
               error_handler=bodhi.server.services.errors.html_handler,
               validators=validators)
def query_users(request):
    db = request.db
    data = request.validated
    query = db.query(User)

    like = data.get('like')
    if like is not None:
        query = query.filter(or_(*[
            User.name.like('%%%s%%' % like)
        ]))

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
        args = \
            [Update.title == update.title for update in updates] +\
            [Update.alias == update.alias for update in updates]
        query = query.filter(or_(*args))

    packages = data.get('packages')
    if packages is not None:
        query = query.join(User.packages)
        query = query.filter(or_(*[RpmPackage.id == p.id for p in packages]))

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
