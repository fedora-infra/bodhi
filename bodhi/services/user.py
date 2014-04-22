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


@user.get(accept=("application/json", "text/json"))
def get_user(request):
    db = request.db
    id = request.matchdict.get('name')
    user = User.get(id, request.db)

    if not user:
        request.errors.add('body', 'name', 'No such user')
        request.errors.status = HTTPNotFound.code
        return

    result = user.__json__()

    # Throw some extra information in there

    # First, build a list of blacklisted user IDs
    #blacklist = ['bodhi', 'autoqa']
    #blacklist = db.query(User).filter(or_(*[User.name==u for u in blacklist]))
    #blacklist = [user.id for user in blacklist.all()]

    # TODO -- don't hardcode this.  2 and 7 are 'bodhi' and 'autoqa'
    blacklist = [2, 7]

    query = request.db.query(Comment)
    query = query.filter(and_(*[Comment.user_id != i for i in blacklist]))

    execute = lambda q: q.order_by(Comment.timestamp.desc()).limit(10).all()
    comments_by = execute(query.filter(Comment.user==user))
    comments_on = execute(query.join(Update).filter(Update.user==user))

    result['comments_by'] = [c.__json__() for c in comments_by]
    result['comments_on'] = [c.__json__() for c in comments_on]

    return result


@user.get(accept="text/html", renderer="user.html")
def get_user_html(request):
    # Re-use the JSON from our own service.
    user = get_user(request)

    if not user:
        raise HTTPNotFound("No such user")

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
