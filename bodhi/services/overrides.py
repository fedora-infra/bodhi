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

from sqlalchemy.sql import or_

from bodhi import log
from bodhi.models import Build, BuildrootOverride, Package, Release
import bodhi.schemas
from bodhi.validators import (validate_override_build, validate_expiration_date,
                              validate_packages, validate_releases,
                              validate_username)


override = Service(name='override', path='/overrides/{nvr}',
                   description='Buildroot Overrides',
                   cors_origins=bodhi.security.cors_origins_ro)

overrides = Service(name='overrides', path='/overrides/',
                    description='Buildroot Overrides',
                    # Note, this 'rw' is not a typo.  the @comments service has
                    # a ``post`` section at the bottom.
                    cors_origins=bodhi.security.cors_origins_rw)


@override.get(accept=("application/json", "text/json"), renderer="json")
@override.get(accept=("application/javascript"), renderer="jsonp")
@override.get(accept=("text/html"), renderer="override.html")
def get_override(request):
    db = request.db
    nvr = request.matchdict.get('nvr')

    build = Build.get(nvr, db)

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


@overrides.get(schema=bodhi.schemas.ListOverrideSchema,
               accept=("application/json", "text/json"), renderer="json",
               validators=(validate_packages, validate_releases,
                           validate_username)
               )
@overrides.get(schema=bodhi.schemas.ListOverrideSchema,
               accept=("application/javascript"), renderer="jsonp",
               validators=(validate_packages, validate_releases,
                           validate_username)
               )
@overrides.get(schema=bodhi.schemas.ListOverrideSchema,
               accept=('application/atom+xml'), renderer='rss',
               validators=(validate_packages, validate_releases,
                           validate_username)
               )
@overrides.get(schema=bodhi.schemas.ListOverrideSchema,
               accept=('text/html'), renderer='overrides.html',
               validators=(validate_packages, validate_releases,
                           validate_username)
               )
def query_overrides(request):
    db = request.db
    data = request.validated
    query = db.query(BuildrootOverride)

    expired = data.get('expired')
    if expired is not None:
        if expired:
            query = query.filter(BuildrootOverride.expired_date!=None)
        else:
            query = query.filter(BuildrootOverride.expired_date==None)

    packages = data.get('packages')
    if packages is not None:
        query = query.join(BuildrootOverride.build).join(Build.package)
        query = query.filter(or_(*[Package.name==pkg.name for pkg in packages]))

    releases = data.get('releases')
    if releases is not None:
        query = query.join(BuildrootOverride.build).join(Build.release)
        query = query.filter(or_(*[Release.name==r.name for r in releases]))

    submitter = data.get('user')
    if submitter is not None:
        query = query.filter(BuildrootOverride.submitter==submitter)

    query = query.order_by(BuildrootOverride.submission_date.desc())
    total = query.count()

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


@overrides.post(schema=bodhi.schemas.SaveOverrideSchema,
                acl=bodhi.security.packagers_allowed_acl,
                accept=("application/json", "text/json"), renderer='json',
                validators=(validate_override_build, validate_expiration_date),
                )
@overrides.post(schema=bodhi.schemas.SaveOverrideSchema,
                acl=bodhi.security.packagers_allowed_acl,
                accept=("application/javascript"), renderer="jsonp",
                validators=(validate_override_build, validate_expiration_date),
                )
def save_override(request):
    """Save a buildroot override

    This entails either creating a new buildroot override, or editing an
    existing one. To edit an existing buildroot override, the buildroot
    override's original id needs to be specified in the ``edited`` parameter.
    """
    data = request.validated

    edited = data.pop("edited")
    build = data['build']

    try:
        if edited is None:
            log.info("Creating a new buildroot override: %s" % data['nvr'])

            override = BuildrootOverride.new(request, build=build,
                                             submitter=request.user,
                                             notes=data['notes'],
                                             expiration_date=data['expiration_date'],
                                             )

        else:
            log.info("Editing buildroot override: %s" % edited)

            edited = Build.get(edited, request.db)

            if edited is None:
                request.errors.add('body', 'edited', 'No such build')
                return

            override = BuildrootOverride.edit(
                    request, edited=edited, submitter=request.user,
                    notes=data["notes"], expired=data["expired"],
                    expiration_date=data["expiration_date"]
                    )

    except Exception as e:
        log.exception(e)
        request.errors.add('body', 'override',
                           'Unable to save buildroot override: %s' % e)
        return

    return override
