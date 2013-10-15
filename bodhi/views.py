import json

from pyramid.view import view_config
from pyramid.exceptions import NotFound
from cornice import Service
from sqlalchemy.sql import or_

from . import log, buildsys
from .models import Bug, Build, CVE, Package, Release, Update, UpdateType
from .schemas import ListUpdateSchema, SaveUpdateSchema
from .security import packagers_allowed_acl
from .validators import (validate_nvrs, validate_version, validate_uniqueness,
        validate_tags, validate_acls, validate_builds, validate_enums,
        validate_releases, validate_username)


updates = Service(name='updates', path='/updates',
                  description='Update submission service',
                  acl=packagers_allowed_acl)


@updates.get(schema=ListUpdateSchema,
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

    releases = data.get('releases')
    if releases is not None:
        query = query.filter(or_(*[Update.release==r for r in releases]))

    releng_approved = data.get('releng_approved')
    if releng_approved is not None:
        query = query.filter_by(releng_approved=releng_approved)

    req = data.get('request')
    if req is not None:
        query = query.filter_by(request=req)

    security_approved = data.get('security_approved')
    if security_approved is not None:
        query = query.filter_by(security_approved=security_approved)

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


@updates.post(schema=SaveUpdateSchema, permission='create',
        validators=(validate_nvrs, validate_version, validate_builds,
                    validate_uniqueness, validate_tags, validate_acls,
                    validate_enums))
def new_update(request):
    """ Save an update.

    This entails either creating a new update, or editing an existing one.
    To edit an existing update, you must specify the update's original
    title in the ``edited`` keyword argument.

    Arguments:
    :builds: A list of koji builds for this update.
    :release: The release that this update is for.
    :type: The type of this update: ``security``, ``bugfix``,
        ``enhancement``, and ``newpackage``.
    :bugs: A list of Red Hat Bugzilla ID's associated with this update.
    :notes: Details as to why this update exists.
    :request: Request for this update to change state, either to
        ``testing``, ``stable``, ``unpush``, ``obsolete`` or None.
    :suggest_reboot: Suggest that the user reboot after update.
    :autokarma: Allow bodhi to automatically change the state of this
        update based on the ``karma`` from user feedback.  It will
        push your update to ``stable`` once it reaches the ``stable_karma``
        and unpush your update when reaching ``unstable_karma``.
    :stable_karma: The upper threshold for marking an update as ``stable``.
    :unstable_karma: The lower threshold for unpushing an update.
    :edited: The update title of the existing update that we are editing.

    """
    data = request.validated
    log.debug('validated = %s' % request.validated)

    try:
        if data.get('edited'):
            log.info('Editing update: %s' % data['edited'])
            up = Update.edit(request, data)
        else:
            log.info('Creating new update: %s' % ' '.join(data['builds']))
            up = Update.new(request, data)
    except:
        log.exception('An unexpected exception has occured')
        request.errors.add('body', 'builds', 'Unable to create update')
        return

    # Bugzilla interactions
    # Set request
    # Critpath checks
    # Send out email notifications

    return up.__json__()


## 404

@view_config(name='notfound_view', renderer='404.html', context=NotFound)
def notfound_view(context, request):
    request.response_status = 404
    return dict()


@view_config(route_name='home', renderer='home.html')
def home(request):
    return {}


@view_config(route_name='metrics', renderer='metrics.html')
def metrics(request):
    db = request.db
    data = []
    ticks = []
    update_types = {
        'bugfix': 'Bug fixes', 'enhancement': 'Enhancements',
        'security': 'Security patches', 'newpackage': 'New packages'
    }
    releases = db.query(Release).filter(Release.name.like('F%')).all()
    for i, release in enumerate(releases):
        ticks.append([i, release.name])
    for update_type, label in update_types.items():
        d = []
        type = UpdateType.from_string(update_type)
        for i, release in enumerate(releases):
            num = db.query(Update).filter_by(release=release, type=type,
                                             status=UpdateStatus.stable).count()
            d.append([i, num])
        data.append(dict(data=d, label=label))
    return {'data': json.dumps(data), 'ticks': json.dumps(ticks)}


def get_all_packages():
    """ Get a list of all packages in Koji """
    log.debug('Fetching list of all packages...')
    koji = buildsys.get_session()
    return [pkg['package_name'] for pkg in koji.listPackages()]


@view_config(route_name='search_pkgs', renderer='json', request_method='GET')
def search_pkgs(request):
    """ Called by the NewUpdateForm.builds AutocompleteWidget """
    packages = get_all_packages()
    return [{'id': p, 'label': p, 'value': p} for p in packages
            if request.GET['term'] in p]


@view_config(route_name='latest_candidates', renderer='json')
def latest_candidates(request):
    """
    For a given `package`, this method returns the most recent builds tagged
    into the Release.candidate_tag for all Releases.
    """
    result = []
    koji = request.koji
    db = request.db
    pkg = request.params.get('package')
    log.debug('latest_candidate(%r)' % pkg)
    if pkg:
        koji.multicall = True
        for release in db.query(Release).all():
            koji.listTagged(release.candidate_tag, package=pkg, latest=True)
        results = koji.multiCall()
        for build in results:
            if build and build[0] and build[0][0]:
                result.append(build[0][0]['nvr'])
    log.debug(result)
    return result
