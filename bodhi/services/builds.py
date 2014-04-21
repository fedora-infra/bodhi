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


build = Service(name='build', path='/builds/{nvr}',
                 description='Koji builds')
builds = Service(name='builds', path='/builds/',
                 description='Koji builds')


@build.get()
def get_build(request):
    nvr = request.matchdict.get('nvr')
    build = request.db.query(Build).filter(Build.nvr==nvr).first()

    if not build:
        request.errors.add('body', 'nvr', 'No such build')
        request.errors.status = HTTPNotFound.code
        return

    return build.__json__()


@builds.get(schema=bodhi.schemas.ListBuildSchema,
             validators=(
                 validate_releases,
                 validate_updates,
                 validate_packages,
             ))
def query_builds(request):
    db = request.db
    data = request.validated
    query = db.query(Build)

    nvr = data.get('nvr')
    if nvr is not None:
        query = query.filter(Build.nvr==nvr)

    updates = data.get('updates')
    if updates is not None:
        query = query.join(Build.update)
        args = \
            [Update.title==update.title for update in updates] +\
            [Update.alias==update.alias for update in updates]
        query = query.filter(or_(*args))

    packages = data.get('packages')
    if packages is not None:
        query = query.join(Build.package)
        query = query.filter(or_(*[Package.id==p.id for p in packages]))

    releases = data.get('releases')
    if releases is not None:
        query = query.join(Build.release)
        query = query.filter(or_(*[Release.id==r.id for r in releases]))


    total = query.count()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    if rows_per_page is None:
        pages = 1
    else:
        pages = int(math.ceil(total / float(rows_per_page)))
        query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(builds=[b.__json__() for b in query],)
