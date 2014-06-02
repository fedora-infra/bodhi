import math

from cornice import Service
from sqlalchemy.sql import or_

from bodhi import log
from bodhi.models import Update, Build, Bug, CVE, Package
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
    validate_releases,
    validate_username,
    validate_update_id,
)


update = Service(name='update', path='/updates/{id}',
                 validators=(validate_update_id,),
                 description='Update submission service')

updates = Service(name='updates', path='/updates/',
                  acl=bodhi.security.packagers_allowed_acl,
                  description='Update submission service')

update_request = Service(name='update_request', path='/updates/{id}/request',
                         description='Update request service',
                         acl=bodhi.security.package_maintainers_only_acl)


@update.get(accept=('application/json', 'text/json'), renderer='json')
@update.get(accept=('application/javascript'), renderer='jsonp')
@update.get(accept="text/html", renderer="update.html")
def get_update(request):
    """Return a single update from an id, title, or alias"""
    return dict(update=request.validated['update'])


@update_request.post(schema=bodhi.schemas.UpdateRequestSchema,
                     validators=(validate_enums, validate_update_id),
                     permission='edit', renderer='json')
def set_request(request):
    """Sets a specific :class:`bodhi.models.UpdateRequest` on a given update"""
    update = request.validated['update']
    action = request.validated['request']
    update.set_request(action, request)
    return dict(update=update)


@updates.get(schema=bodhi.schemas.ListUpdateSchema,
             accept=('application/json', 'text/json'), renderer='json',
             validators=(
                 validate_releases,
                 validate_enums,
                 validate_username,
             ))
@updates.get(schema=bodhi.schemas.ListUpdateSchema,
             accept=('application/javascript'), renderer='jsonp',
             validators=(
                 validate_releases,
                 validate_enums,
                 validate_username,
             ))
@updates.get(schema=bodhi.schemas.ListUpdateSchema,
             accept=('text/html'), renderer='updates.html',
             validators=(
                 validate_releases,
                 validate_enums,
                 validate_username,
             ))
def query_updates(request):
    db = request.db
    data = request.validated
    query = db.query(Update)

    approved_since = data.get('approved_since')
    if approved_since is not None:
        query = query.filter(Update.date_approved >= approved_since)

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

    packages = data.get('packages')
    if packages is not None:
        query = query.join(Update.builds).join(Build.package)
        query = query.filter(or_(*[Package.name==pkg for pkg in packages]))

    pushed = data.get('pushed')
    if pushed is not None:
        query = query.filter(Update.pushed==pushed)

    pushed_since = data.get('pushed_since')
    if pushed_since is not None:
        query = query.filter(Update.date_pushed >= pushed_since)

    releases = data.get('releases')
    if releases is not None:
        query = query.filter(or_(*[Update.release==r for r in releases]))

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

    suggest = data.get('suggest')
    if suggest is not None:
        query = query.filter(Update.suggest==suggest)

    type = data.get('type')
    if type is not None:
        query = query.filter(Update.type==type)

    user = data.get('user')
    if user is not None:
        query = query.filter(Update.user==user)

    query = query.order_by(Update.date_submitted.desc())
    total = query.count()

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
    )


@updates.post(schema=bodhi.schemas.SaveUpdateSchema,
              permission='create', renderer='json',
              validators=(
                  validate_nvrs, validate_version, validate_builds,
                  validate_uniqueness, validate_tags, validate_acls,
                  validate_enums))
def new_update(request):
    """ Save an update.

    This entails either creating a new update, or editing an existing one. To
    edit an existing update, the update's original title must be specified in
    the ``edited`` parameter.
    """
    data = request.validated
    log.debug('validated = %s' % data)
    req = data.get('request')
    del(data['request'])

    try:
        if data.get('edited'):
            log.info('Editing update: %s' % data['edited'])
            up = Update.edit(request, data)
        else:
            log.info('Creating new update: %s' % ' '.join(data['builds']))
            up = Update.new(request, data)
            log.debug('update = %r' % up)
    except Exception as e:
        log.exception(e)
        request.errors.add('body', 'builds', 'Unable to create update')
        return

    up.obsolete_older_updates(request)

    # Set request
    if req:
        up.set_request(req, request)

    # Send out email notifications

    return up
