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

import copy
import math

from cornice import Service
from sqlalchemy import func, distinct
from sqlalchemy.sql import or_

from bodhi import log
from bodhi.exceptions import BodhiException, LockedUpdateException
from bodhi.models import Update, Build, Bug, CVE, Package, UpdateRequest, ReleaseState
import bodhi.schemas
import bodhi.security
import bodhi.services.errors
import bodhi.util
from bodhi.validators import (
    validate_nvrs,
    validate_uniqueness,
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
)


update = Service(name='update', path='/updates/{id}',
                 validators=(validate_update_id,),
                 description='Update submission service',
                 acl=bodhi.security.packagers_allowed_acl,
                 cors_origins=bodhi.security.cors_origins_ro)

update_edit = Service(name='update_edit', path='/updates/{id}/edit',
                 validators=(validate_update_id,),
                 description='Update submission service',
                 acl=bodhi.security.packagers_allowed_acl,
                 cors_origins=bodhi.security.cors_origins_rw)

updates = Service(name='updates', path='/updates/',
                  acl=bodhi.security.packagers_allowed_acl,
                  description='Update submission service',
                  cors_origins=bodhi.security.cors_origins_ro)

updates_rss = Service(name='updates_rss', path='/rss/updates/',
                      acl=bodhi.security.packagers_allowed_acl,
                      description='Update submission service RSS feed',
                      cors_origins=bodhi.security.cors_origins_ro)

update_request = Service(name='update_request', path='/updates/{id}/request',
                         description='Update request service',
                         acl=bodhi.security.packagers_allowed_acl,
                         cors_origins=bodhi.security.cors_origins_rw)

@update.get(accept=('application/json', 'text/json'), renderer='json',
            error_handler=bodhi.services.errors.json_handler)
@update.get(accept=('application/javascript'), renderer='jsonp',
            error_handler=bodhi.services.errors.jsonp_handler)
@update.get(accept="text/html", renderer="update.html",
            error_handler=bodhi.services.errors.html_handler)
def get_update(request):
    """Return a single update from an id, title, or alias"""

    proxy_request = bodhi.security.ProtectedRequest(request)
    validate_acls(proxy_request)
    # If validate_acls produced 0 errors, then we can edit this update.
    can_edit = len(proxy_request.errors) == 0

    return dict(update=request.validated['update'], can_edit=can_edit)


@update_edit.get(accept="text/html", renderer="new_update.html",
                 error_handler=bodhi.services.errors.html_handler)
def get_update_for_editing(request):
    """Return a single update from an id, title, or alias for the edit form"""
    return dict(
        update=request.validated['update'],
        types=reversed(bodhi.models.UpdateType.values()),
        severities=sorted(bodhi.models.UpdateSeverity.values(), key=bodhi.util.sort_severity),
        suggestions=reversed(bodhi.models.UpdateSuggestion.values()),
    )


@update_request.post(schema=bodhi.schemas.UpdateRequestSchema,
                     validators=(
                         validate_enums,
                         validate_update_id,
                         validate_build_tags,
                         validate_acls,
                         validate_request,
                     ),
                     permission='edit', renderer='json',
                     error_handler=bodhi.services.errors.json_handler)
def set_request(request):
    """Sets a specific :class:`bodhi.models.UpdateRequest` on a given update"""
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

    if action is UpdateRequest.stable:
        settings = request.registry.settings
        result, reason = update.check_requirements(request.db, settings)
        if not result:
            request.errors.add('body', 'request',
                               'Requirement not met %s' % reason)
            return

    try:
        update.set_request(request.db, action, request.user.name)
    except BodhiException as e:
        log.exception("Failed to set the request")
        request.errors.add('body', 'request', str(e))
    except Exception as e:
        log.exception("Unhandled exception in set_request")
        request.errors.add('body', 'request', str(e))

    return dict(update=update)


validators = (
    validate_release,
    validate_releases,
    validate_enums,
    validate_username,
    validate_bugs,
)
@updates_rss.get(schema=bodhi.schemas.ListUpdateSchema, renderer='rss',
                 error_handler=bodhi.services.errors.html_handler,
                 validators=validators)
@updates.get(schema=bodhi.schemas.ListUpdateSchema,
             accept=('application/json', 'text/json'), renderer='json',
             error_handler=bodhi.services.errors.json_handler,
             validators=validators)
@updates.get(schema=bodhi.schemas.ListUpdateSchema,
             accept=('application/javascript'), renderer='jsonp',
             error_handler=bodhi.services.errors.jsonp_handler,
             validators=validators)
@updates.get(schema=bodhi.schemas.ListUpdateSchema,
             accept=('text/html'), renderer='updates.html',
             error_handler=bodhi.services.errors.html_handler,
             validators=validators)
def query_updates(request):
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
        query = query.filter(or_(*[Bug.bug_id==bug_id for bug_id in bugs]))

    critpath = data.get('critpath')
    if critpath is not None:
        query = query.filter(Update.critpath==critpath)

    cves = data.get('cves')
    if cves is not None:
        query = query.join(Update.cves)
        query = query.filter(or_(*[CVE.cve_id==cve_id for cve_id in cves]))

    like = data.get('like')
    if like is not None:
        query = query.filter(or_(*[
            Update.title.like('%%%s%%' % like)
        ]))

    locked = data.get('locked')
    if locked is not None:
        query = query.filter(Update.locked==locked)

    modified_since = data.get('modified_since')
    if modified_since is not None:
        query = query.filter(Update.date_modified >= modified_since)

    modified_before = data.get('modified_before')
    if modified_before is not None:
        query = query.filter(Update.date_modified < modified_before)

    packages = data.get('packages')
    if packages is not None:
        query = query.join(Update.builds).join(Build.package)
        query = query.filter(or_(*[Package.name==pkg for pkg in packages]))

    package = None
    if packages and len(packages):
        package = packages[0]

    builds = data.get('builds')
    if builds is not None:
        query = query.join(Update.builds)
        query = query.filter(or_(*[Build.nvr==build for build in builds]))

    pushed = data.get('pushed')
    if pushed is not None:
        query = query.filter(Update.pushed==pushed)

    pushed_since = data.get('pushed_since')
    if pushed_since is not None:
        query = query.filter(Update.date_pushed >= pushed_since)

    pushed_before = data.get('pushed_before')
    if pushed_before is not None:
        query = query.filter(Update.date_pushed < pushed_before)

    releases = data.get('releases')
    if releases is not None:
        query = query.filter(or_(*[Update.release==r for r in releases]))

    # This singular version of the plural "releases" is purely for bodhi1
    # backwards compat (mostly for RSS feeds) - threebean
    release = data.get('release')
    if release is not None:
        query = query.filter(Update.release==release)

    req = data.get('request')
    if req is not None:
        query = query.filter(Update.request==req)

    severity = data.get('severity')
    if severity is not None:
        query = query.filter(Update.severity==severity)

    status = data.get('status')
    if status is not None:
        query = query.filter(Update.status==status)

    submitted_since = data.get('submitted_since')
    if submitted_since is not None:
        query = query.filter(Update.date_submitted >= submitted_since)

    submitted_before = data.get('submitted_before')
    if submitted_before is not None:
        query = query.filter(Update.date_submitted < submitted_before)

    suggest = data.get('suggest')
    if suggest is not None:
        query = query.filter(Update.suggest==suggest)

    type = data.get('type')
    if type is not None:
        query = query.filter(Update.type==type)

    user = data.get('user')
    if user is not None:
        query = query.filter(Update.user==user)

    updateid = data.get('updateid')
    if updateid is not None:
        query = query.filter(or_(*[Update.alias==uid for uid in updateid]))
    alias = data.get('alias')
    if alias is not None:
        query = query.filter(or_(*[Update.alias==a for a in alias]))

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


@updates.post(schema=bodhi.schemas.SaveUpdateSchema,
              permission='create', renderer='json',
              error_handler=bodhi.services.errors.json_handler,
              validators=(
                  validate_nvrs,
                  validate_builds,
                  validate_uniqueness,
                  validate_build_tags,
                  validate_acls,
                  validate_enums,
                  validate_requirements,
                  validate_bugs,
              ))
def new_update(request):
    """ Save an update.

    This entails either creating a new update, or editing an existing one. To
    edit an existing update, the update's original title must be specified in
    the ``edited`` parameter.
    """
    data = request.validated
    log.debug('validated = %s' % data)

    # This has already been validated at this point, but we need to ditch
    # it since the models don't care about a csrf argument.
    data.pop('csrf_token')

    caveats = []
    try:

        releases = set()
        builds = []

        # Create the Package and Build entities
        for nvr in data['builds']:
            name, version, release = request.buildinfo[nvr]['nvr']
            package = request.db.query(Package).filter_by(name=name).first()
            if not package:
                package = Package(name=name)
                request.db.add(package)
                request.db.flush()

            build = Build.get(nvr, request.db)

            if build is None:
                log.debug("Adding nvr %s", nvr)
                build = Build(nvr=nvr, package=package)
                request.db.add(build)
                request.db.flush()

            build.package = package
            build.release = request.buildinfo[build.nvr]['release']
            builds.append(build)
            releases.add(request.buildinfo[build.nvr]['release'])


        if data.get('edited'):

            log.info('Editing update: %s' % data['edited'])

            assert len(releases) == 1, "Updates may not span multiple releases"
            data['release'] = list(releases)[0]
            data['builds'] = [b.nvr for b in builds]
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

                log.info('Creating new update: %r' % _data['builds'])
                result, _caveats = Update.new(request, _data)
                log.debug('%s update created', result.title)

                updates.append(result)
                caveats.extend(_caveats)

            if len(releases) > 1:
                result = dict(updates=updates)
    except LockedUpdateException as e:
        log.warn(str(e))
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
