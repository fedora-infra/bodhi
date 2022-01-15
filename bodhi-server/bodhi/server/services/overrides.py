# Copyright © 2014-2017 Red Hat, Inc. and others.
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
"""Define API endpoints for managing and searching buildroot overrides."""

import math
from datetime import datetime

from cornice import Service
from cornice.validators import colander_body_validator, colander_querystring_validator
from pyramid.exceptions import HTTPNotFound
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_

from bodhi.server import log, security
from bodhi.server.models import Build, BuildrootOverride, Package, Release, User
import bodhi.server.schemas
import bodhi.server.services.errors
from bodhi.server.validators import (
    validate_override_builds,
    validate_expiration_date,
    validate_override_notes,
    validate_packages,
    validate_releases,
    validate_username,
)


override = Service(name='override', path='/overrides/{nvr}',
                   description='Buildroot Overrides',
                   cors_origins=bodhi.server.security.cors_origins_ro)

overrides = Service(name='overrides', path='/overrides/',
                    description='Buildroot Overrides',
                    factory=security.PackagerACLFactory,
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
    """
    Return a dictionary with key "override" indexing the override that matches the given nvr.

    Args:
        request (pyramid.request): The current request, which should have a query parameter "nvr",
            providing the nvr of the requested override.
    Returns:
        dict: A dictionary with key "override" that indexes the override matching the given nvr.
    """
    nvr = request.matchdict.get('nvr')

    build = Build.get(nvr)

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
    colander_querystring_validator,
    validate_packages,
    validate_releases,
    validate_username,
)


@overrides_rss.get(schema=bodhi.server.schemas.ListOverrideSchema, renderer='rss',
                   error_handler=bodhi.server.services.errors.html_handler,
                   validators=validators)
@overrides.get(schema=bodhi.server.schemas.ListOverrideSchema, renderer='rss',
               accept=('application/atom+xml',),
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
    """
    Search for overrides by various criteria.

    The following optional parameters may be used when searching for overrides:
        builds (list): A list of NVRs to search overrides by.
        expired (bool): If True, limit search to expired overrides. If False, limit search to active
            overrides.
        like (str): Perform an SQL "like" query against build NVRs with the given string.
        packages (list): A list of package names to search overrides by.
        releases (list): A list of release names to limit the overrides search by.
        search (str): Perform an SQL "ilike" query against build NVRs with the given string.
        submitter (str): Search for overrides submitted by the given username.

    Returns:
        dict: A dictionary with the following keys:
            overrides: An iterable containing the matched overrides.
            page: The current page number in the results.
            pages: The number of pages of results that match the query.
            rows_per_page: The number of rows on the page.
            total: The total number of overrides that match the criteria.
            chrome: The caller supplied chrome.
            display_user: The current username.
    """
    db = request.db
    data = request.validated
    query = db.query(BuildrootOverride)

    expired = data.get('expired')
    if expired is not None:
        if expired:
            query = query.filter(BuildrootOverride.expired_date.isnot(None))
        else:
            query = query.filter(BuildrootOverride.expired_date.is_(None))

    builds = data.get('builds')
    if builds is not None:
        query = query.join(BuildrootOverride.build)
        query = query.filter(or_(*[Build.nvr == bld for bld in builds]))

    packages = data.get('packages')
    if packages is not None:
        query = query.join(BuildrootOverride.build).join(Build.package)
        query = query.filter(or_(*[Package.name == pkg.name for pkg in packages]))

    releases = data.get('releases')
    if releases is not None:
        query = query.join(BuildrootOverride.build).join(Build.release)
        query = query.filter(or_(*[Release.name == r.name for r in releases]))

    like = data.get('like')
    if like is not None:
        query = query.join(BuildrootOverride.build)
        query = query.filter(or_(*[
            Build.nvr.like('%%%s%%' % like)
        ]))

    search = data.get('search')
    if search is not None:
        query = query.join(BuildrootOverride.build)
        query = query.filter(Build.nvr.ilike('%%%s%%' % search))

    submitter = data.get('user')
    if submitter is not None:
        query = query.filter(or_(*[BuildrootOverride.submitter == s for s in submitter]))

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

    return_values = dict(
        overrides=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
        chrome=data.get('chrome'),
        display_user=data.get('display_user'),
    )
    # we need some extra information for the searching / filterings interface
    # when rendering the html, so we add this here.
    if request.accept.accept_html():
        return_values.update(
            releases=Release.all_releases(),
        )
    return return_values


@overrides.post(schema=bodhi.server.schemas.SaveOverrideSchema,
                permission='edit',
                accept=("application/json", "text/json"), renderer='json',
                error_handler=bodhi.server.services.errors.json_handler,
                validators=(
                    colander_body_validator,
                    validate_override_builds,
                    validate_expiration_date,
                    validate_override_notes,
                ))
@overrides.post(schema=bodhi.server.schemas.SaveOverrideSchema,
                permission='edit',
                accept=("application/javascript"), renderer="jsonp",
                error_handler=bodhi.server.services.errors.jsonp_handler,
                validators=(
                    colander_body_validator,
                    validate_override_builds,
                    validate_expiration_date,
                    validate_override_notes,
                ))
def save_override(request):
    """
    Create or edit a buildroot override.

    This entails either creating a new buildroot override, or editing an
    existing one. To edit an existing buildroot override, the buildroot
    override's original id needs to be specified in the ``edited`` parameter.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: The new or edited override.
    """
    data = request.validated

    edited = data.pop("edited")

    caveats = []
    try:
        submitter = User.get(request.user.name)
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
                existing_override = BuildrootOverride.get(build.id)
                if existing_override:
                    if not existing_override.expired_date:
                        data['expiration_date'] = max(existing_override.expiration_date,
                                                      data['expiration_date'])

                    new_notes = f"""{data['notes']}
_____________
_@{existing_override.submitter.name} ({existing_override.submission_date.strftime('%b %d, %Y')})_
{existing_override.notes}"""
                    # Truncate notes at 2000 chars
                    if len(new_notes) > 2000:
                        new_notes = new_notes[:1972] + '(...)\n___Notes truncated___'

                    overrides.append(BuildrootOverride.edit(
                        request,
                        edited=build,
                        submitter=submitter,
                        submission_date=datetime.now(),
                        notes=new_notes,
                        expiration_date=data['expiration_date'],
                        expired=None,
                    ))
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

            edited = Build.get(edited)

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
