from cornice import Service
from pyramid.exceptions import HTTPNotFound
from sqlalchemy.sql import or_

import math

from bodhi import log
from bodhi.models import Update, Build, Bug, CVE, Package, User, Release, Group
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


@user.get(accept=("application/json", "text/json"))
def get_user(request):
    id = request.matchdict.get('name')
    user = User.get(id, request.db)

    if not user:
        request.errors.add('body', 'name', 'No such user')
        request.errors.status = HTTPNotFound.code
        return

    return user.__json__()

@user.get(accept="text/html", renderer="user.html")
def get_user_html(request):
    # Re-use the JSON from our own service.
    user = get_user(request)

    if not user:
        raise HTTPNotFound("No such user %r" % id)

    return dict(user=user)


@users.get(schema=bodhi.schemas.ListUserSchema,
           validators=(validate_groups, validate_updates, validate_packages))
def query_users(request):
    db = request.db
    data = request.validated
    query = db.query(User)

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
    if rows_per_page is None:
        pages = 1
    else:
        pages = int(math.ceil(total / float(rows_per_page)))
        query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(users=[u.__json__() for u in query])
