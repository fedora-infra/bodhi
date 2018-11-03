# -*- coding: utf-8 -*-
# Copyright © 2014-2018 Red Hat Inc., and others.
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
"""Defines API endpoints related to Release objects."""

import math

from cornice import Service
from cornice.validators import colander_body_validator, colander_querystring_validator
from pyramid.exceptions import HTTPNotFound
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_

from bodhi.server import log, security
from bodhi.server.models import (
    Update,
    UpdateStatus,
    UpdateType,
    Build,
    BuildrootOverride,
    Package,
    Release,
    ReleaseState,
)
from bodhi.server.validators import (
    validate_tags,
    validate_enums,
    validate_updates,
    validate_packages,
    validate_release,
)
import bodhi.server.schemas
import bodhi.server.services.errors


release = Service(name='release', path='/releases/{name}',
                  description='Fedora Releases',
                  cors_origins=bodhi.server.security.cors_origins_ro)
releases = Service(name='releases', path='/releases/',
                   description='Fedora Releases',
                   factory=security.AdminACLFactory,
                   # Note, this 'rw' is not a typo.  the @comments service has
                   # a ``post`` section at the bottom.
                   cors_origins=bodhi.server.security.cors_origins_rw)


@release.get(accept="text/html", renderer="release.html",
             error_handler=bodhi.server.services.errors.html_handler)
def get_release_html(request):
    """
    Render a release given by id as HTML.

    Args:
        request (pyramid.Request): The current request.
    Returns:
        basestring: An HTML representation of the reqeusted Release.
    """
    id = request.matchdict.get('name')
    release = Release.get(id)
    if not release:
        request.errors.add('body', 'name', 'No such release')
        request.errors.status = HTTPNotFound.code
    updates = request.db.query(Update).filter(Update.release == release).order_by(
        Update.date_submitted.desc())

    updates_count = request.db.query(Update.date_submitted, Update.type).filter(
        Update.release == release).order_by(Update.date_submitted.desc())

    date_commits = {}
    dates = set()

    for update in updates_count.all():
        d = update.date_submitted
        yearmonth = str(d.year) + '/' + str(d.month).zfill(2)
        dates.add(yearmonth)
        if update.type.description not in date_commits:
            date_commits[update.type.description] = {}
        if yearmonth in date_commits[update.type.description]:
            date_commits[update.type.description][yearmonth] += 1
        else:
            date_commits[update.type.description][yearmonth] = 0

    base_count_query = request.db.query(Update)\
        .filter(Update.release == release)

    num_updates_pending = base_count_query\
        .filter(Update.status == UpdateStatus.pending).count()
    num_updates_testing = base_count_query\
        .filter(Update.status == UpdateStatus.testing).count()
    num_updates_stable = base_count_query\
        .filter(Update.status == UpdateStatus.stable).count()
    num_updates_unpushed = base_count_query\
        .filter(Update.status == UpdateStatus.unpushed).count()
    num_updates_obsolete = base_count_query\
        .filter(Update.status == UpdateStatus.obsolete).count()

    num_updates_security = base_count_query\
        .filter(Update.type == UpdateType.security).count()
    num_updates_bugfix = base_count_query\
        .filter(Update.type == UpdateType.bugfix).count()
    num_updates_enhancement = base_count_query\
        .filter(Update.type == UpdateType.enhancement).count()
    num_updates_newpackage = base_count_query\
        .filter(Update.type == UpdateType.newpackage).count()

    num_active_overrides = request.db.query(
        BuildrootOverride
    ).filter(
        BuildrootOverride.expired_date.is_(None)
    ).join(
        BuildrootOverride.build
    ).join(
        Build.release
    ).filter(
        Build.release == release
    ).count()

    num_expired_overrides = request.db.query(
        BuildrootOverride
    ).filter(
        BuildrootOverride.expired_date.isnot(None)
    ).join(
        BuildrootOverride.build
    ).join(
        Build.release
    ).filter(
        Build.release == release
    ).count()

    return dict(release=release,
                latest_updates=updates.limit(25).all(),
                count=updates.count(),
                date_commits=date_commits,
                dates=sorted(dates),

                num_updates_pending=num_updates_pending,
                num_updates_testing=num_updates_testing,
                num_updates_stable=num_updates_stable,
                num_updates_unpushed=num_updates_unpushed,
                num_updates_obsolete=num_updates_obsolete,

                num_updates_security=num_updates_security,
                num_updates_bugfix=num_updates_bugfix,
                num_updates_enhancement=num_updates_enhancement,
                num_updates_newpackage=num_updates_newpackage,

                num_active_overrides=num_active_overrides,
                num_expired_overrides=num_expired_overrides,
                )


@release.get(accept=('application/json', 'text/json'), renderer='json',
             error_handler=bodhi.server.services.errors.json_handler)
@release.get(accept=('application/javascript'), renderer='jsonp',
             error_handler=bodhi.server.services.errors.jsonp_handler)
def get_release_json(request):
    """
    Return JSON for a release given by name.

    Args:
        request (pyramid.json): The current request.
    Returns:
        bodhi.server.models.Release: The matched Release.
    """
    id = request.matchdict.get('name')
    release = Release.get(id)
    if not release:
        request.errors.add('body', 'name', 'No such release')
        request.errors.status = HTTPNotFound.code
    return release


releases_get_validators = (colander_querystring_validator, validate_release, validate_updates,
                           validate_packages)


@releases.get(accept="text/html", schema=bodhi.server.schemas.ListReleaseSchema,
              renderer='releases.html',
              error_handler=bodhi.server.services.errors.html_handler,
              validators=releases_get_validators)
def query_releases_html(request):
    """
    Return all releases, collated by state, rendered as HTML.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary with a single key, releases, mapping another dictionary that maps release
            states to a list of Release objects that are in that state.
    """
    def collect_releases(releases):
        x = {}
        for r in releases:
            if r['state'] in x:
                x[r['state']].append(r)
            else:
                x[r['state']] = [r]
        return x

    db = request.db
    releases = db.query(Release).order_by(Release.id.desc()).all()
    return dict(releases=collect_releases(releases))


@releases.get(accept=('application/json', 'text/json'),
              schema=bodhi.server.schemas.ListReleaseSchema, renderer='json',
              error_handler=bodhi.server.services.errors.json_handler,
              validators=releases_get_validators)
def query_releases_json(request):
    """
    Search releases by given criteria, returning the results as JSON.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary with the following keys:
            releases: An iterable of the Releases that match the query.
            page: The current page.
            pages: The total number of pages.
            rows_per_page: The number of rown on a page.
            total: The number of matching results.
    """
    db = request.db
    data = request.validated
    query = db.query(Release)

    ids = data.get('ids')
    if ids is not None:
        query = query.filter(or_(*[Release.id == _id for _id in ids]))

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

    exclude_archived = data.get('exclude_archived')
    if exclude_archived:
        query = query.filter(Release.state != ReleaseState.archived)

    state = data.get('state')
    if state is not None:
        query = query.filter(Release.state == ReleaseState.from_string(state))

    # We can't use ``query.count()`` here because it is naive with respect to
    # all the joins that we're doing above.
    count_query = query.with_labels().statement\
        .with_only_columns([func.count(distinct(Release.id))])\
        .order_by(None)
    total = db.execute(count_query).scalar()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        releases=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
    )


@releases.post(schema=bodhi.server.schemas.SaveReleaseSchema,
               permission='admin', renderer='json',
               error_handler=bodhi.server.services.errors.json_handler,
               validators=(colander_body_validator, validate_tags, validate_enums)
               )
def save_release(request):
    """
    Save a release.

    This entails either creating a new release, or editing an existing one. To
    edit an existing release, the release's original name must be specified in
    the ``edited`` parameter.

    Args:
        request (pyramid.request): The current request.
    Returns:
        bodhi.server.models.Request: The created or edited Request.
    """
    data = request.validated

    edited = data.pop("edited", None)

    # This has already been validated at this point, but we need to ditch
    # it since the models don't care about a csrf argument.
    data.pop('csrf_token', None)

    try:
        if edited is None:
            log.info("Creating a new release: %s" % data['name'])
            r = Release(**data)

        else:
            log.info("Editing release: %s" % edited)
            r = request.db.query(Release).filter(Release.name == edited).one()
            for k, v in data.items():
                setattr(r, k, v)

    except Exception as e:
        log.exception(e)
        request.errors.add('body', 'release',
                           'Unable to create/edit release: %s' % e)
        return

    request.db.add(r)
    request.db.flush()

    return r
