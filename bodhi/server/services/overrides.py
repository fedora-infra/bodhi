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

from bodhi.server import log
from bodhi.server.models import Build, BuildrootOverride, RpmPackage, Release, RpmBuild, User
import bodhi.server.schemas
import bodhi.server.services.errors
from bodhi.server.validators import (
    validate_override_builds,
    validate_expiration_date,
    validate_packages,
    validate_releases,
    validate_username,
)


override = Service(name='override', path='/overrides/{nvr}',
                   description='Buildroot Overrides',
                   cors_origins=bodhi.server.security.cors_origins_ro)

overrides = Service(name='overrides', path='/overrides/',
                    description='Buildroot Overrides',
                    # Note, this 'rw' is not a typo.  the @comments service has
                    # a ``post`` section at the bottom.
                    cors_origins=bodhi.server.security.cors_origins_rw)

overrides_rss = Service(name='overrides_rss', path='/rss/overrides/',
                        description='Buildroot Overrides RSS Feed',
                        cors_origins=bodhi.server.security.cors_origins_ro)


@override.get(accept=("application/json", "text/json"), renderer="json",
              error_handler=bodhi.server.services.errors.json_handler)
@override.get(accept=("application/javascript"), renderer="jsonp",
              error_handler=bodhi.server.services.errors.jsonp_handler)
@override.get(accept=("text/html"), renderer="override.html",
              error_handler=bodhi.server.services.errors.html_handler)
def get_override(request):
    db = request.db
    nvr = request.matchdict.get('nvr')

    build = RpmBuild.get(nvr, db)

    if not build:
        request.errors.add('url', 'nvr', 'No such build')
        request.errors.status = HTTPNotFound.code
        return

    if not build.override:
        request.errors.add('url', 'nvr',
                           'No buildroot override for this build')
        request.errors.status = HTTPNotFound.code
        return

    return dict(override=build.override)


validators = (
    validate_packages,
    validate_releases,
    validate_username,
)


@overrides_rss.get(schema=bodhi.server.schemas.ListOverrideSchema, renderer='rss',
                   error_handler=bodhi.server.services.errors.html_handler,
                   validators=validators)
@overrides.get(schema=bodhi.server.schemas.ListOverrideSchema,
               accept=("application/json", "text/json"), renderer="json",
               error_handler=bodhi.server.services.errors.json_handler,
               validators=validators)
@overrides.get(schema=bodhi.server.schemas.ListOverrideSchema,
               accept=("application/javascript"), renderer="jsonp",
               error_handler=bodhi.server.services.errors.jsonp_handler,
               validators=validators)
@overrides.get(schema=bodhi.server.schemas.ListOverrideSchema,
               accept=('text/html'), renderer='overrides.html',
               error_handler=bodhi.server.services.errors.html_handler,
               validators=validators)
def query_overrides(request):
    db = request.db
    data = request.validated
    query = db.query(BuildrootOverride)

    expired = data.get('expired')
    if expired is not None:
        if expired:
            query = query.filter(BuildrootOverride.expired_date.isnot(None))
        else:
            query = query.filter(BuildrootOverride.expired_date.is_(None))

    packages = data.get('packages')
    if packages is not None:
        query = query.join(BuildrootOverride.build).join(Build.package)
        query = query.filter(or_(*[RpmPackage.name == pkg.name for pkg in packages]))

    releases = data.get('releases')
    if releases is not None:
        query = query.join(BuildrootOverride.build).join(Build.release)
        query = query.filter(or_(*[Release.name == r.name for r in releases]))

    like = data.get('like')
    if like is not None:
        query = query.join(BuildrootOverride.build)
        query = query.filter(or_(*[
            RpmBuild.nvr.like('%%%s%%' % like)
        ]))

    submitter = data.get('user')
    if submitter is not None:
        query = query.filter(BuildrootOverride.submitter == submitter)

    query = query.order_by(BuildrootOverride.submission_date.desc())

    # We can't use ``query.count()`` here because it is naive with respect to
    # all the joins that we're doing above.
    count_query = query.with_labels().statement\
        .with_only_columns([func.count(distinct(BuildrootOverride.id))])\
        .order_by(None)
    total = db.execute(count_query).scalar()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        overrides=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
        chrome=data.get('chrome'),
        display_user=data.get('display_user'),
    )


@overrides.post(schema=bodhi.server.schemas.SaveOverrideSchema,
                acl=bodhi.server.security.packagers_allowed_acl,
                accept=("application/json", "text/json"), renderer='json',
                error_handler=bodhi.server.services.errors.json_handler,
                validators=(
                    validate_override_builds,
                    validate_expiration_date,
                ))
@overrides.post(schema=bodhi.server.schemas.SaveOverrideSchema,
                acl=bodhi.server.security.packagers_allowed_acl,
                accept=("application/javascript"), renderer="jsonp",
                error_handler=bodhi.server.services.errors.jsonp_handler,
                validators=(
                    validate_override_builds,
                    validate_expiration_date,
                ))
def save_override(request):
    """Save a buildroot override

    This entails either creating a new buildroot override, or editing an
    existing one. To edit an existing buildroot override, the buildroot
    override's original id needs to be specified in the ``edited`` parameter.
    """
    data = request.validated

    edited = data.pop("edited")

    caveats = []
    try:
        submitter = User.get(request.user.name, request.db)
        if edited is None:
            builds = data['builds']
            overrides = []
            if len(builds) > 1:
                caveats.append({
                    'name': 'nvrs',
                    'description': 'Your override submission was '
                    'split into %i.' % len(builds)
                })
            for build in builds:
                log.info("Creating a new buildroot override: %s" % build.nvr)
                if BuildrootOverride.get(build.id, request.db):
                    request.errors.add('body', 'builds',
                                       'Buildroot override for %s already exists' % build.nvr)
                    return
                else:
                    overrides.append(BuildrootOverride.new(
                        request,
                        build=build,
                        submitter=submitter,
                        notes=data['notes'],
                        expiration_date=data['expiration_date'],
                    ))

            if len(builds) > 1:
                result = dict(overrides=overrides)
            else:
                result = overrides[0]
        else:
            log.info("Editing buildroot override: %s" % edited)

            edited = RpmBuild.get(edited, request.db)

            if edited is None:
                request.errors.add('body', 'edited', 'No such build')
                return

            result = BuildrootOverride.edit(
                request, edited=edited, submitter=submitter,
                notes=data["notes"], expired=data["expired"],
                expiration_date=data["expiration_date"])

            if not result:
                # Some error inside .edit(...)
                return

    except Exception as e:
        log.exception(e)
        request.errors.add('body', 'override',
                           'Unable to save buildroot override: %s' % e)
        return

    if not isinstance(result, dict):
        result = result.__json__()

    result['caveats'] = caveats

    return result
