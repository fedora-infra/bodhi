# -*- coding: utf-8 -*-
# Copyright © 2015-2017 Red Hat, Inc.
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
"""Define a service endpoint for searching for packages."""
import math

from cornice import Service
from cornice.validators import colander_querystring_validator
from sqlalchemy import func, distinct
from sqlalchemy.sql.expression import case

from bodhi.server.models import Package
import bodhi.server.schemas
import bodhi.server.security
import bodhi.server.services.errors


packages = Service(name='packages', path='/packages/',
                   description='PkgDB packages',
                   cors_origins=bodhi.server.security.cors_origins_ro)


@packages.get(
    schema=bodhi.server.schemas.ListPackageSchema, renderer='json',
    error_handler=bodhi.server.services.errors.json_handler,
    validators=(colander_querystring_validator,))
def query_packages(request):
    """
    Search for packages via query string parameters.

    The following query string parameters may be used to limit the packages returned by the service:
        name: The name of the Packages you wish to retrieve.
        like: Search for Packages with names like the given string.
        search: Search for Packages with names like the given string, with case insensitivity.
        page: Retrieve the specified page of search results.
        rows_per_page: Specify how many rows per page are desired.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: A dictionary with the following key value mappings:
            packages: An iterable of packages that match the search criteria.
            page: The current page of results.
            pages: The number of pages of results.
            rows_per_page: The number of results per page.
            total: The total number of packages that match the search criteria.
    """
    db = request.db
    data = request.validated
    query = db.query(Package)

    name = data.get('name')
    if name is not None:
        query = query.filter(Package.name == name)

    like = data.get('like')
    if like is not None:
        query = query.filter(Package.name.like('%%%s%%' % like))

    search = data.get('search')
    if search is not None:
        query = query.filter(Package.name.ilike('%%%s%%' % search))
        query = query.order_by(case([(Package.name == search, Package.name)]))

    # We can't use ``query.count()`` here because it is naive with respect to
    # all the joins that we're doing above.
    count_query = query.with_labels().statement\
        .with_only_columns([func.count(distinct(Package.name))])\
        .order_by(None)
    total = db.execute(count_query).scalar()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        packages=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
    )
