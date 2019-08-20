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
"""Defines service endpoints pertaining to Updates."""

import copy
import math

from cornice import Service
from cornice.validators import colander_body_validator, colander_querystring_validator
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_
from requests import RequestException, Timeout as RequestsTimeout

from bodhi.server import log, security
from bodhi.server.exceptions import BodhiException, LockedUpdateException
from bodhi.server.models import (
    Update,
    Bug,
    ContentType,
    UpdateRequest,
    ReleaseState,
    Build,
    Package,
)
import bodhi.server.schemas
import bodhi.server.services.errors
import bodhi.server.util
from bodhi.server.validators import (
    validate_builds_or_from_tag_exist,
    validate_build_nvrs,
    validate_build_uniqueness,
    validate_build_tags,
    validate_acls,
    validate_builds,
    validate_enums,
    validate_releases,
    validate_release,
    validate_username,
    validate_update_id,
    validate_requirements,
    validate_bugs,
    validate_request,
    validate_severity,
    validate_from_tag,
)


update = Service(name='update', path='/updates/{id}',
                 validators=(validate_update_id,),
                 description='Update submission service',
                 factory=security.PackagerACLFactory,
                 cors_origins=bodhi.server.security.cors_origins_ro)

update_edit = Service(
    name='update_edit', path='/updates/{id}/edit', validators=(validate_update_id,),
    description='Update submission service', factory=security.PackagerACLFactory,
    cors_origins=bodhi.server.security.cors_origins_rw)

updates = Service(name='updates', path='/updates/',
                  factory=security.PackagerACLFactory,
                  description='Update submission service',
                  cors_origins=bodhi.server.security.cors_origins_ro)

updates_rss = Service(name='updates_rss', path='/rss/updates/',
                      factory=security.PackagerACLFactory,
                      description='Update submission service RSS feed',
                      cors_origins=bodhi.server.security.cors_origins_ro)

update_request = Service(name='update_request', path='/updates/{id}/request',
                         description='Update request service',
                         factory=security.PackagerACLFactory,
                         cors_origins=bodhi.server.security.cors_origins_rw)

update_waive_test_results = Service(
    name='update_waive_test_results',
    path='/updates/{id}/waive-test-results',
    description='Waive test results that block transitioning the update to next state',
    factory=security.PackagerACLFactory,
    cors_origins=bodhi.server.security.cors_origins_rw
)

update_get_test_results = Service(
    name='update_get_test_results',
    path='/updates/{id}/get-test-results',
    description='Get test results for a specified update',
    cors_origins=bodhi.server.security.cors_origins_ro,
)


@update.get(accept=('application/json', 'text/json'), renderer='json',
            error_handler=bodhi.server.services.errors.json_handler)
@update.get(accept=('application/javascript'), renderer='jsonp',
            error_handler=bodhi.server.services.errors.jsonp_handler)
@update.get(accept="text/html", renderer="update.html",
            error_handler=bodhi.server.services.errors.html_handler)
def get_update(request):
    """
    Return a single update from an id or alias.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary with the following key mappings:
            update: The update that was requested.
            can_edit: A boolean indicating whether the update can be edited.
    """
    proxy_request = bodhi.server.security.ProtectedRequest(request)
    validate_acls(proxy_request)
    # If validate_acls produced 0 errors, then we can edit this update.
    can_edit = len(proxy_request.errors) == 0

    return dict(update=request.validated['update'], can_edit=can_edit)


@update_edit.get(accept="text/html", renderer="new_update.html",
                 error_handler=bodhi.server.services.errors.html_handler,
                 permission='edit',
                 validators=(
                     validate_acls,
                 ))
def get_update_for_editing(request):
    """
    Return a single update from an id or alias for the edit form.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary with the following key mappings:
            update: The update to be edited.
            types: The possible values for update types.
            severities: The possible values for update severity.
            suggestions: The possible values for update suggestion.
    """
    suggestions = list(bodhi.server.models.UpdateSuggestion.values())
    return dict(
        update=request.validated['update'],
        types=reversed(list(bodhi.server.models.UpdateType.values())),
        severities=sorted(
            list(bodhi.server.models.UpdateSeverity.values()), key=bodhi.server.util.sort_severity),
        suggestions=suggestions,
    )


@update_request.post(schema=bodhi.server.schemas.UpdateRequestSchema,
                     validators=(
                         colander_body_validator,
                         validate_enums,
                         validate_update_id,
                         validate_build_tags,
                         validate_acls,
                         validate_request,
                     ),
                     permission='edit', renderer='json',
                     error_handler=bodhi.server.services.errors.json_handler)
def set_request(request):
    """
    Set a specific :class:`bodhi.server.models.UpdateRequest` on a given update.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary mapping the key "update" to the update that was modified.
    """
    update = request.validated['update']
    action = request.validated['request']

    if update.locked:
        request.errors.add('body', 'request',
                           "Can't change request on a locked update")
        return

    if update.release.state is ReleaseState.archived:
        request.errors.add('body', 'request',
                           "Can't change request for an archived release")
        return

    if action == UpdateRequest.stable:
        settings = request.registry.settings
        result, reason = update.check_requirements(request.db, settings)
        log.info(
            f'Unable to set request for {update.alias} to {action} due to failed requirements: '
            f'{reason}')
        if not result:
            request.errors.add('body', 'request',
                               'Requirement not met %s' % reason)
            return

    try:
        update.set_request(request.db, action, request.user.name)
    except BodhiException as e:
        log.info("Failed to set the request: %s", e)
        request.errors.add('body', 'request', str(e))
    except Exception as e:
        log.exception("Unhandled exception in set_request")
        request.errors.add('body', 'request', str(e))

    return dict(update=update)


validators = (
    colander_querystring_validator,
    validate_release,
    validate_releases,
    validate_enums,
    validate_username,
    validate_bugs,
)


@updates_rss.get(schema=bodhi.server.schemas.ListUpdateSchema, renderer='rss',
                 error_handler=bodhi.server.services.errors.html_handler,
                 validators=validators)
@updates.get(schema=bodhi.server.schemas.ListUpdateSchema, renderer='rss',
             accept=('application/atom+xml',),
             error_handler=bodhi.server.services.errors.html_handler,
             validators=validators)
@updates.get(schema=bodhi.server.schemas.ListUpdateSchema,
             accept=('application/json', 'text/json'), renderer='json',
             error_handler=bodhi.server.services.errors.json_handler,
             validators=validators)
@updates.get(schema=bodhi.server.schemas.ListUpdateSchema,
             accept=('application/javascript'), renderer='jsonp',
             error_handler=bodhi.server.services.errors.jsonp_handler,
             validators=validators)
@updates.get(schema=bodhi.server.schemas.ListUpdateSchema,
             accept=('text/html'), renderer='updates.html',
             error_handler=bodhi.server.services.errors.html_handler,
             validators=validators)
def query_updates(request):
    """
    Search updates by given criteria.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary with at least the following key mappings:
            updates: An iterable of the updates that match the query.
            page: The current page.
            pages: The total number of pages.
            rows_per_page: How many results on on the page.
            total: The total number of updates matching the query.
            package: The package corresponding to the first update found in the search.
    """
    db = request.db
    data = request.validated
    query = db.query(Update)

    approved_since = data.get('approved_since')
    if approved_since is not None:
        query = query.filter(Update.date_approved >= approved_since)

    approved_before = data.get('approved_before')
    if approved_before is not None:
        query = query.filter(Update.date_approved < approved_before)

    bugs = data.get('bugs')
    if bugs is not None:
        query = query.join(Update.bugs)
        query = query.filter(or_(*[Bug.bug_id == bug_id for bug_id in bugs]))

    critpath = data.get('critpath')
    if critpath is not None:
        query = query.filter(Update.critpath == critpath)

    like = data.get('like')
    if like is not None:
        query = query.join(Update.builds)
        query = query.filter(Build.nvr.like('%%%s%%' % like))

    search = data.get('search')
    if search is not None:
        query = query.join(Update.builds)
        query = query.filter(or_(
            Build.nvr.ilike('%%%s%%' % search), Update.alias.ilike('%%%s%%' % search)))

    locked = data.get('locked')
    if locked is not None:
        query = query.filter(Update.locked == locked)

    modified_since = data.get('modified_since')
    if modified_since is not None:
        query = query.filter(Update.date_modified >= modified_since)

    modified_before = data.get('modified_before')
    if modified_before is not None:
        query = query.filter(Update.date_modified < modified_before)

    packages = data.get('packages')
    if packages is not None:
        query = query.join(Update.builds).join(Build.package)
        query = query.filter(or_(*[Package.name == pkg for pkg in packages]))

    package = None
    if packages and len(packages):
        package = packages[0]

    builds = data.get('builds')
    if builds is not None:
        query = query.join(Update.builds)
        query = query.filter(or_(*[Build.nvr == build for build in builds]))

    pushed = data.get('pushed')
    if pushed is not None:
        query = query.filter(Update.pushed == pushed)

    pushed_since = data.get('pushed_since')
    if pushed_since is not None:
        query = query.filter(Update.date_pushed >= pushed_since)

    pushed_before = data.get('pushed_before')
    if pushed_before is not None:
        query = query.filter(Update.date_pushed < pushed_before)

    releases = data.get('releases')
    if releases is not None:
        query = query.filter(or_(*[Update.release == r for r in releases]))

    # This singular version of the plural "releases" is purely for bodhi1
    # backwards compat (mostly for RSS feeds) - threebean
    release = data.get('release')
    if release is not None:
        query = query.filter(Update.release == release)

    req = data.get('request')
    if req is not None:
        query = query.filter(Update.request == req)

    severity = data.get('severity')
    if severity is not None:
        query = query.filter(Update.severity == severity)

    status = data.get('status')
    if status is not None:
        query = query.filter(Update.status == status)

    submitted_since = data.get('submitted_since')
    if submitted_since is not None:
        query = query.filter(Update.date_submitted >= submitted_since)

    submitted_before = data.get('submitted_before')
    if submitted_before is not None:
        query = query.filter(Update.date_submitted < submitted_before)

    suggest = data.get('suggest')
    if suggest is not None:
        query = query.filter(Update.suggest == suggest)

    type = data.get('type')
    if type is not None:
        query = query.filter(Update.type == type)

    content_type = data.get('content_type')
    if content_type is not None:
        query = query.join(Update.builds)
        query = query.filter(Build.type == content_type)

    gating_status = data.get('gating')
    if gating_status is not None:
        query = query.filter(Update.test_gating_status == gating_status)

    user = data.get('user')
    if user is not None:
        query = query.filter(or_(*[Update.user == u for u in user]))

    updateid = data.get('updateid')
    if updateid is not None:
        query = query.filter(or_(*[Update.alias == uid for uid in updateid]))
    alias = data.get('alias')
    if alias is not None:
        query = query.filter(or_(*[Update.alias == a for a in alias]))

    query = query.order_by(Update.date_submitted.desc())

    # We can't use ``query.count()`` here because it is naive with respect to
    # all the joins that we're doing above.
    count_query = query.with_labels().statement\
        .with_only_columns([func.count(distinct(Update.id))])\
        .order_by(None)
    total = db.execute(count_query).scalar()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        updates=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
        chrome=data.get('chrome'),
        display_user=data.get('display_user', False),
        display_request=data.get('display_request', True),
        package=package,
    )


@updates.post(schema=bodhi.server.schemas.SaveUpdateSchema,
              permission='create', renderer='json',
              error_handler=bodhi.server.services.errors.json_handler,
              validators=(
                  colander_body_validator,
                  validate_build_nvrs,
                  validate_builds,
                  validate_build_tags,
                  validate_build_uniqueness,
                  validate_from_tag,
                  validate_builds_or_from_tag_exist,
                  validate_acls,
                  validate_enums,
                  validate_requirements,
                  validate_bugs,
                  validate_severity,
              ))
def new_update(request):
    """
    Save an update.

    This entails either creating a new update, or editing an existing one. To
    edit an existing update, the update's alias must be specified in
    the ``edited`` parameter.

    If the ``from_tag`` parameter is specified and ``builds`` is missing or
    empty, the list of builds will be filled with the latest builds in this
    Koji tag. This is done by validate_from_tag() because the list of builds
    needs to be available in validate_acls().

    Args:
        request (pyramid.request): The current request.
    """
    data = request.validated
    log.debug('validated = %s' % data)

    # This has already been validated at this point, but we need to ditch
    # it since the models don't care about a csrf argument.
    data.pop('csrf_token')

    # Same here, but it can be missing.
    data.pop('builds_from_tag', None)

    build_nvrs = data.get('builds', [])
    from_tag = data.get('from_tag')

    caveats = []
    try:

        releases = set()
        builds = []

        # Create the Package and Build entities
        for nvr in build_nvrs:
            name, version, release = request.buildinfo[nvr]['nvr']

            package = Package.get_or_create(request.buildinfo[nvr])

            # Also figure out the build type and create the build if absent.
            build_class = ContentType.infer_content_class(
                base=Build, build=request.buildinfo[nvr]['info'])
            build = build_class.get(nvr)

            if build is None:
                log.debug("Adding nvr %s, type %r", nvr, build_class)
                build = build_class(nvr=nvr, package=package)
                request.db.add(build)
                request.db.flush()

            build.package = package
            build.release = request.buildinfo[build.nvr]['release']
            builds.append(build)
            releases.add(request.buildinfo[build.nvr]['release'])

        # We want to go ahead and commit the transaction now so that the Builds are in the database.
        # Otherwise, there will be a race condition between robosignatory signing the Builds and the
        # signed handler attempting to mark the builds as signed. When we lose that race, the signed
        # handler doesn't see the Builds in the database and gives up. After that, nothing will mark
        # the builds as signed.
        request.db.commit()

        # After we commit the transaction, we need to get the builds and releases again, since they
        # were tied to the previous session that has now been terminated.
        builds = []
        releases = set()
        for nvr in build_nvrs:
            # At this moment, we are sure the builds are in the database (that is what the commit
            # was for actually).
            build = Build.get(nvr)
            builds.append(build)
            releases.add(build.release)

        if data.get('edited'):

            log.info('Editing update: %s' % data['edited'])

            data['release'] = list(releases)[0]
            data['builds'] = [b.nvr for b in builds]
            data['from_tag'] = from_tag
            result, _caveats = Update.edit(request, data)
            caveats.extend(_caveats)
        else:
            if len(releases) > 1:
                caveats.append({
                    'name': 'releases',
                    'description': 'Your update is being split '
                    'into %i, one for each release.' % len(releases)

                })
            updates = []
            for release in releases:
                _data = copy.copy(data)  # Copy it because .new(..) mutates it
                _data['builds'] = [b for b in builds if b.release == release]
                _data['release'] = release
                _data['from_tag'] = from_tag

                log.info('Creating new update: %r' % _data['builds'])
                result, _caveats = Update.new(request, _data)
                log.debug('%s update created', result.alias)

                updates.append(result)
                caveats.extend(_caveats)

            if len(releases) > 1:
                result = dict(updates=updates)
    except LockedUpdateException as e:
        log.warning(str(e))
        request.errors.add('body', 'builds', "%s" % str(e))
        return
    except Exception as e:
        log.exception('Failed to create update')
        request.errors.add(
            'body', 'builds', 'Unable to create update.  %s' % str(e))
        return

    # Obsolete older updates for three different cases...
    # editing an update, submitting a new single update, submitting multiple.

    if isinstance(result, dict):
        updates = result['updates']
    else:
        updates = [result]

    for update in updates:
        try:
            caveats.extend(update.obsolete_older_updates(request.db))
        except Exception as e:
            caveats.append({
                'name': 'update',
                'description': 'Problem obsoleting older updates: %s' % str(e),
            })

    if not isinstance(result, dict):
        result = result.__json__()

    result['caveats'] = caveats

    return result


@update_waive_test_results.post(schema=bodhi.server.schemas.WaiveTestResultsSchema,
                                validators=(colander_body_validator,
                                            validate_update_id,
                                            validate_acls),
                                permission='edit', renderer='json',
                                error_handler=bodhi.server.services.errors.json_handler)
def waive_test_results(request):
    """
    Waive all blocking test results on a given update when gating is on.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary mapping the key "update" to the update.
    """
    update = request.validated['update']
    comment = request.validated.pop('comment', None)
    tests = request.validated.pop('tests', None)

    try:
        update.waive_test_results(request.user.name, comment, tests)
    except LockedUpdateException as e:
        log.warning(str(e))
        request.errors.add('body', 'request', str(e))
    except BodhiException as e:
        log.error("Failed to waive the test results: %s", e)
        request.errors.add('body', 'request', str(e))
    except Exception as e:
        log.exception("Unhandled exception in waive_test_results")
        request.errors.add('body', 'request', str(e))

    return dict(update=update)


@update_get_test_results.get(schema=bodhi.server.schemas.GetTestResultsSchema,
                             validators=(validate_update_id),
                             renderer='json',
                             error_handler=bodhi.server.services.errors.json_handler)
def get_test_results(request):
    """
    Get the test results on a given update when gating is on.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary mapping the key "update" to the update.
    """
    update = request.validated['update']

    decision = None
    try:
        decision = update.get_test_gating_info()
    except RequestsTimeout as e:
        log.error("Error querying greenwave for test results - timed out")
        request.errors.add('body', 'request', str(e))
        request.errors.status = 504
    except (RequestException, RuntimeError) as e:
        log.error("Error querying greenwave for test results: %s", e)
        request.errors.add('body', 'request', str(e))
        request.errors.status = 502
    except BodhiException as e:
        log.error("Failed to query greenwave for test results: %s", e)
        request.errors.add('body', 'request', str(e))
        request.errors.status = 501
    except Exception as e:
        log.exception("Unhandled exception in get_test_results")
        request.errors.add('body', 'request', str(e))
        request.errors.status = 500

    return dict(decision=decision)
