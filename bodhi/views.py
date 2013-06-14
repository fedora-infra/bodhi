import rpm
import logging
import colander

from pprint import pprint
from beaker.cache import cache_region
from webhelpers.html.grid import Grid
from webhelpers.paginate import Page, PageURL_WebOb
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.exceptions import NotFound, Forbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember, authenticated_userid, forget
from pyramid.security import Allow, Deny, Everyone, Authenticated, ALL_PERMISSIONS, DENY_ALL

from bodhi import buildsys
from bodhi.models import DBSession, Release, Build, Package, User, Group, Update
#from bodhi.widgets import NewUpdateForm
from bodhi.util import _, get_nvr
from bodhi.schemas import UpdateSchema
from bodhi.validators import (validate_nvrs, validate_version,
        validate_uniqueness, validate_tags, validate_acls,
        validate_builds)

log = logging.getLogger(__name__)


from cornice import Service
from cornice.resource import resource, view


def admin_only_acl(request):
    """Generate our admin-only ACL"""
    return  [(Allow, 'group:' + group, ALL_PERMISSIONS) for group in
             request.registry.settings['admin_packager_groups'].split()]


def packagers_allowed_acl(request):
    """Generate an ACL for update submission"""
    return [(Allow, 'group:' + group, ALL_PERMISSIONS) for group in
            request.registry.settings['mandatory_packager_groups'].split()] + \
           [DENY_ALL]


updates = Service(name='updates', path='/updates',
                  description='Update submission service',
                  acl=packagers_allowed_acl)


@updates.get()
def query_updates(request):
    # TODO: flexible querying api.
    session = DBSession()
    return dict(updates=[u.__json__() for u in session.query(Update).all()])



@updates.post(schema=UpdateSchema, permission='create',
        validators=(validate_nvrs, validate_version, validate_builds,
                    validate_uniqueness, validate_tags, validate_acls))
def new_update(request):
    log.debug('validated = %s' % request.validated)
    # TODO:
    # Editing magic
    # Create model instances
    # Obsolete any older updates, inherit data
    # Bugzilla interactions
    # Security checks
    # Critpath checks
    # Look for test cases on the wiki
    # Set request
    # Send out email notifications
    return {}


## 404

@view_config(name='notfound_view', renderer='404.html', context=NotFound)
def notfound_view(context, request):
    request.response_status = 404
    return dict()


@view_config(route_name='home', renderer='home.html')
def home(request):
    return {}


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
    koji = buildsys.get_session()
    pkg = request.params.get('package')
    log.debug('latest_candidate(%r)' % pkg)
    if pkg:
        session = DBSession()
        koji.multicall = True
        for release in session.query(Release).all():
            koji.listTagged(release.candidate_tag, package=pkg, latest=True)
        results = koji.multiCall()
        for build in results:
            if build and build[0] and build[0][0]:
                result.append(build[0][0]['nvr'])
    log.debug(result)
    return result


def login(request):
    login_url = request.route_url('login')
    referrer = request.url
    if referrer == login_url:
        referrer = request.route_url('home')
    came_from = request.params.get('came_from', referrer)
    request.session['came_from'] = came_from
    oid_url = request.registry.settings['openid.provider']
    return HTTPFound(location=request.route_url('verify_openid',
                                                _query=dict(openid=oid_url)))


def logout(request):
    headers = forget(request)
    return HTTPFound(location=request.route_url('home'), headers=headers)


def remember_me(context, request, info, *args, **kw):
    log.debug('remember_me(%s)' % locals())
    log.debug('request.params = %r' % request.params)
    endpoint = request.params['openid.op_endpoint']
    if endpoint != request.registry.settings['openid.provider']:
        log.warn('Invalid OpenID provider: %s' % endpoint)
        request.session.flash('Invalid OpenID provider. You can only use: %s' %
                              request.registry.settings['openid.provider'])
        return HTTPFound(location=request.route_url('home'))
    username = info['identity_url'].split('http://')[1].split('.')[0]
    log.debug('%s successfully logged in' % username)
    log.debug('groups = %s' % info['groups'])

    # Find the user in our database. Create it if it doesn't exist.
    session = DBSession()
    user = session.query(User).filter_by(name=username).first()
    if not user:
        user = User(name=username)
        session.add(user)
        session.flush()

    # See if they are a member of any important groups
    important_groups = request.registry.settings['important_groups'].split()
    for important_group in important_groups:
        if important_group in info['groups']:
            group = session.query(Group).filter_by(name=important_group).first()
            if not group:
                group = Group(name=important_group)
                session.add(group)
                session.flush()
            user.groups.append(group)

    headers = remember(request, username)
    came_from = request.session['came_from']
    del(request.session['came_from'])
    response = HTTPFound(location=came_from)
    response.headerlist.extend(headers)
    return response
