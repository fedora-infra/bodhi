from itertools import ifilter
import json

from pprint import pprint
from beaker.cache import cache_region
from webhelpers.html.grid import Grid
from webhelpers.paginate import Page, PageURL_WebOb
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.exceptions import NotFound, Forbidden
from cornice import Service
from sqlalchemy.sql import or_

from . import log, buildsys
from .models import Release, Build, Package, User, Group, Update, UpdateStatus
from .models import UpdateRequest, UpdateSeverity, UpdateType, UpdateSuggestion
from .util import _, get_nvr
from .schemas import UpdateSchema
from .security import admin_only_acl, packagers_allowed_acl
from .validators import (validate_nvrs, validate_version, validate_uniqueness,
        validate_tags, validate_acls, validate_builds, validate_enums,
        validate_releases, validate_request, validate_status, validate_type,
        validate_username, validate_critpath, validate_submitted_since)


updates = Service(name='updates', path='/updates',
                  description='Update submission service',
                  acl=packagers_allowed_acl)


@updates.get(validators=(validate_releases, validate_request, validate_status,
                         validate_type, validate_username, validate_critpath,
                         validate_submitted_since))
def query_updates(request):
    # TODO: flexible querying api.
    db = request.db
    data = request.validated
    query = db.query(Update)

    releases = data.get('releases')
    if releases:
        query = query.filter(or_(*[Update.release==r for r in releases]))

    req = data.get('request')
    if req:
        query = query.filter_by(request=req)

    status = data.get('status')
    if status:
        query = query.filter_by(status=status)

    type = data.get('type')
    if type:
        query = query.filter_by(type=type)

    user = data.get('user')
    if user:
        query = query.filter(Update.user==user)

    critpath = data.get('critpath')
    if critpath is not None:
        # TODO: Try using a view?
        query = ifilter(lambda u: u.critpath == critpath, query)

    submitted_since = data.get('submitted_since')
    if submitted_since:
        query = query.filter(Update.date_submitted >= submitted_since)

    return dict(updates=[u.__json__() for u in query])


@updates.post(schema=UpdateSchema, permission='create',
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
