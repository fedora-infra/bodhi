from cornice import Service
from pyramid.exceptions import HTTPNotFound
from sqlalchemy.sql import or_

import math

from bodhi import log
from bodhi.models import Update, Build, Bug, CVE, Package, User, Release, Group
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
    validate_releases,
    validate_release,
    validate_username,
    validate_groups,
)


release = Service(name='release', path='/releases/{name}',
                  description='Fedora Releases')
releases = Service(name='releases', path='/releases/',
                   description='Fedora Releases')


@release.get()
def get_release(request):
    id = request.matchdict.get('name')
    release = request.db.query(Release).filter(or_(
        Release.id == id,
        Release.name == id,
        Release.long_name == id,
        Release.dist_tag == id,
    )).first()

    if not release:
        request.errors.add('body', 'name', 'No such release')
        request.errors.status = HTTPNotFound.code
        return

    return release.__json__()


@releases.get(schema=bodhi.schemas.ListReleaseSchema,
              validators=(
                  validate_release,
                  validate_updates,
                  validate_packages,
              ))
def query_releases(request):
    db = request.db
    data = request.validated
    query = db.query(Release)

    name = data.get('name')
    if name is not None:
        query = query.filter(Release.name.like(name))

    updates = data.get('updates')
    if updates is not None:
        query = query.join(Release.builds).join(Build.update)
        args = \
            [Update.title == update.title for update in updates] +\
            [Update.alias == update.alias for update in updates]
        query = query.filter(or_(*args))

    packages = data.get('packages')
    if packages is not None:
        query = query.join(Release.builds).join(Build.package)
        query = query.filter(or_(*[Package.id == p.id for p in packages]))

    total = query.count()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    if rows_per_page is None:
        pages = 1
    else:
        pages = int(math.ceil(total / float(rows_per_page)))
        query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(releases=[r.__json__() for r in query])
