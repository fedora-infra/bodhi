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

from cornice import Service
from pyramid.exceptions import HTTPNotFound
from sqlalchemy.sql import or_, and_

import math

from bodhi import log
from bodhi.models import Update, Package, User, Comment, Group
import bodhi.services.updates
import bodhi.schemas
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
    validate_releases,
    validate_release,
    validate_username,
    validate_groups,
)


user = Service(name='user', path='/users/{name}',
                 description='Bodhi users')
users = Service(name='users', path='/users/',
                 description='Bodhi users')


@user.get(accept=("application/json", "text/json"), renderer="json")
@user.get(accept=("application/javascript"), renderer="jsonp")
@user.get(accept="text/html", renderer="user.html")
def get_user(request):
    db = request.db
    id = request.matchdict.get('name')
    user = User.get(id, request.db)

    if not user:
        request.errors.add('body', 'name', 'No such user')
        request.errors.status = HTTPNotFound.code
        return

    result = user.__json__(request)

    # Throw some extra information in there

    # First, build a blacklist of users whose comments we don't want to see.
    blacklist = request.registry.settings.get('system_users').split()
    blacklist = db.query(User)\
        .filter(or_(*[User.name == name for name in blacklist]))
    blacklist = [u.id for u in blacklist]

    query = db.query(Comment)
    query = query.filter(and_(*[Comment.user_id != i for i in blacklist]))

    # Then, make a couple different queries
    execute = lambda q: q.order_by(Comment.timestamp.desc()).limit(10).all()
    comments_by = execute(query.filter(Comment.user==user))
    comments_on = execute(query.join(Update).filter(Update.user==user))

    updates = db.query(Update)\
        .filter(Update.user == user)\
        .order_by(Update.date_submitted.desc())\
        .limit(14).all()

    # And stuff the results in the dict
    result['comments_by'] = comments_by
    result['comments_on'] = comments_on
    result['recent_updates'] = updates

    return dict(user=result)


@users.get(schema=bodhi.schemas.ListUserSchema,
           accept=("application/json", "text/json"), renderer="json",
           validators=(validate_groups, validate_updates, validate_packages))
@users.get(schema=bodhi.schemas.ListUserSchema,
           accept=("application/javascript"), renderer="jsonp",
           validators=(validate_groups, validate_updates, validate_packages))
@users.get(schema=bodhi.schemas.ListUserSchema,
           accept=("application/rss"), renderer="rss",
           validators=(validate_groups, validate_updates, validate_packages))
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
        query = query.filter(or_(*[Group.id==grp.id for grp in groups]))

    updates = data.get('updates')
    if updates is not None:
        query = query.join(User.updates)
        args = \
            [Update.title==update.title for update in updates] +\
            [Update.alias==update.alias for update in updates]
        query = query.filter(or_(*args))

    packages = data.get('packages')
    if packages is not None:
        query = query.join(User.packages)
        query = query.filter(or_(*[Package.id==p.id for p in packages]))

    total = query.count()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(users=query.all())
