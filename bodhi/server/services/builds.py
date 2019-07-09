# Copyright © 2014-2019 Red Hat, Inc. and others.
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
"""Define service endpoint for retrieving Builds."""
import math

from cornice import Service
from cornice.validators import colander_querystring_validator
from pyramid.exceptions import HTTPNotFound
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_

from bodhi.server.models import Update, Build, Package, Release
from bodhi.server.validators import (validate_updates,
                                     validate_packages, validate_releases)
import bodhi.server.schemas
import bodhi.server.security
import bodhi.server.services.errors


build = Service(name='build', path='/builds/{nvr}', description='Koji builds',
                cors_origins=bodhi.server.security.cors_origins_ro)
builds = Service(name='builds', path='/builds/',
                 description='Koji builds',
                 cors_origins=bodhi.server.security.cors_origins_ro)


@build.get(renderer='json',
           error_handler=bodhi.server.services.errors.json_handler)
def get_build(request):
    """
    Retrieve a Build by name-version-release, specified via an "nvr" query string parameter.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        bodhi.server.models.Build or None: The Build matching the search, or None if there is no
            Build with the given NVR.
    """
    nvr = request.matchdict.get('nvr')
    build = Build.get(nvr)
    if not build:
        request.errors.add('body', 'nvr', 'No such build')
        request.errors.status = HTTPNotFound.code
        return
    return build


@builds.get(schema=bodhi.server.schemas.ListBuildSchema, renderer='json',
            error_handler=bodhi.server.services.errors.json_handler,
            validators=(colander_querystring_validator, validate_releases, validate_updates,
                        validate_packages))
def query_builds(request):
    """
    Search for Builds by given criteria.

    The following criteria can be provided via query string parameters to search for Builds:
        nvr: The dash-separated name-version-release of a Build.
        updates: A space or comma separated list of updates to limit the search by.
        packages: A space or comma separated list of packages to search for builds by.
        releases: A space or comma separated list of release ids to limit builds by.
        page: Which page of search results are desired.
        rows_per_pags: How many results per page are desired.

    Args:
        request (pyramid.request): The current request, containing the search criteria documented
            above.
    Returns:
        dict: A dictionary with the following key value mappings:
            builds: An iterable of builds that match the search criteria, ordered by nvr.
            page: The current page.
            pages: The total number of pages.
            rows_per_page: The number of rows per page.
            total: The number of builds that match the search criteria.
    """
    db = request.db
    data = request.validated
    query = db.query(Build).order_by(Build.nvr.asc())

    nvr = data.get('nvr')
    if nvr is not None:
        query = query.filter(Build.nvr == nvr)

    updates = data.get('updates')
    if updates is not None:
        query = query.join(Build.update)
        args = [Update.alias == update.alias for update in updates]
        query = query.filter(or_(*args))

    packages = data.get('packages')
    if packages is not None:
        query = query.join(Build.package)
        query = query.filter(or_(*[Package.id == p.id for p in packages]))

    releases = data.get('releases')
    if releases is not None:
        query = query.join(Build.release)
        query = query.filter(or_(*[Release.id == r.id for r in releases]))

    # We can't use ``query.count()`` here because it is naive with respect to
    # all the joins that we're doing above.
    count_query = query.with_labels().statement\
        .with_only_columns([func.count(distinct(Build.nvr))])\
        .order_by(None)
    total = db.execute(count_query).scalar()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        builds=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
    )
