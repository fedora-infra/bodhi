from cornice import Service
from sqlalchemy.sql import or_

from bodhi import log
from bodhi.models import Update, Build, Bug, CVE, Package, User, Release
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
)


update = Service(name='update', path='/updates/{id}',
                 description='Update submission service')

updates = Service(name='updates', path='/updates/',
                  description='Update submission service',
                  acl=bodhi.security.packagers_allowed_acl)

user = Service(name='user', path='/user/{name}',
               description='Bodhi users')

release = Service(name='release', path='/release/{name}',
                  description='Fedora Releases')


@update.get()
def get_update(request):
    db = request.db
    id = request.matchdict.get('id')
    upd = db.query(Update).filter(or_(
        Update.id==id,
        Update.title==id,
        Update.alias==id,
    )).first()

    if not upd:
        request.errors.add('body', 'id', 'No such update.')
        return

    return upd.__json__()


@updates.get(schema=bodhi.schemas.ListUpdateSchema,
             validators=(validate_releases, validate_enums, validate_username))
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
        query = query.filter_by(critpath=critpath)

    cves = data.get('cves')
    if cves is not None:
        query = query.join(Update.cves)
        query = query.filter(or_(*[CVE.cve_id==cve_id for cve_id in cves]))

    locked = data.get('locked')
    if locked is not None:
        query = query.filter_by(locked=locked)

    modified_since = data.get('modified_since')
    if modified_since is not None:
        query = query.filter(Update.date_modified >= modified_since)

    packages = data.get('packages')
    if packages is not None:
        query = query.join(Update.builds).join(Build.package)
        query = query.filter(or_(*[Package.name==pkg for pkg in packages]))

    pushed = data.get('pushed')
    if pushed is not None:
        query = query.filter_by(pushed=pushed)

    pushed_since = data.get('pushed_since')
    if pushed_since is not None:
        query = query.filter(Update.date_pushed >= pushed_since)

    qa_approved = data.get('qa_approved')
    if qa_approved is not None:
        query = query.filter_by(qa_approved=qa_approved)

    qa_approved_since = data.get('qa_approved_since')
    if qa_approved_since is not None:
        query = query.filter(Update.qa_approval_date >= qa_approved_since)

    releases = data.get('releases')
    if releases is not None:
        query = query.filter(or_(*[Update.release==r for r in releases]))

    releng_approved = data.get('releng_approved')
    if releng_approved is not None:
        query = query.filter_by(releng_approved=releng_approved)

    releng_approved_since = data.get('releng_approved_since')
    if releng_approved_since is not None:
        query = query.filter(Update.releng_approval_date >= releng_approved_since)

    req = data.get('request')
    if req is not None:
        query = query.filter_by(request=req)

    security_approved = data.get('security_approved')
    if security_approved is not None:
        query = query.filter_by(security_approved=security_approved)

    security_approved_since = data.get('security_approved_since')
    if security_approved_since is not None:
        query = query.filter(Update.security_approval_date >= security_approved_since)

    severity = data.get('severity')
    if severity is not None:
        query = query.filter_by(severity=severity)

    status = data.get('status')
    if status is not None:
        query = query.filter_by(status=status)

    submitted_since = data.get('submitted_since')
    if submitted_since is not None:
        query = query.filter(Update.date_submitted >= submitted_since)

    suggest = data.get('suggest')
    if suggest is not None:
        query = query.filter_by(suggest=suggest)

    type = data.get('type')
    if type is not None:
        query = query.filter_by(type=type)

    user = data.get('user')
    if user is not None:
        query = query.filter(Update.user==user)

    return dict(updates=[u.__json__() for u in query])


@updates.post(schema=bodhi.schemas.SaveUpdateSchema,
              permission='create',
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
    except:
        log.exception('An unexpected exception has occured')
        request.errors.add('body', 'builds', 'Unable to create update')
        return

    up.obsolete_older_updates(request)

    # Set request
    if req:
        try:
            up.set_request(req, request)
        except:
            log.exception('Problem setting request')

    # Send out email notifications

    return up.__json__()


@user.get()
def get_user(request):
    db = request.db
    id = request.matchdict.get('name')
    user = db.query(User).filter(or_(
        User.id==id,
        User.name==id,
    )).first()

    if not user:
        request.errors.add('body', 'name', 'No such .')
        return

    return user.__json__()


@release.get()
def get_release(request):
    db = request.db
    id = request.matchdict.get('name')
    release = db.query(Release).filter(or_(
        Release.id==id,
        Release.name==id,
    )).first()

    if not release:
        request.errors.add('body', 'name', 'No such .')
        return

    return release.__json__()
