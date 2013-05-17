import rpm
import logging
import tw2.core

from pprint import pprint
from beaker.cache import cache_region
from webhelpers.html.grid import Grid
from webhelpers.paginate import Page, PageURL_WebOb
from pyramid.url import route_url
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.security import remember, authenticated_userid, forget
from pyramid.httpexceptions import HTTPFound

from bodhi import buildsys
from bodhi.models import DBSession, Release, Build, Package
from bodhi.widgets import NewUpdateForm
from bodhi.util import _, get_nvr

log = logging.getLogger(__name__)

## JSON views


def view_model_instance_json(context, request):
    return {'context': context.__json__()}


def view_model_json(context, request):
    session = DBSession()
    entries = session.query(context.__model__)
    current_page = int(request.params.get('page', 1))
    items_per_page = int(request.params.get('items_per_page', 20))
    page = Page(entries, page=current_page, items_per_page=items_per_page)
    return {'entries': [entry.__json__() for entry in page]}

## Mako templated views


def view_model_instance(context, request):
    return {'context': context}


def view_model(context, request):
    session = DBSession()
    entries = session.query(context.__model__)
    current_page = int(request.params.get('page', 1))
    items_per_page = int(request.params.get('items_per_page', 20))
    page_url = PageURL_WebOb(request)
    page = Page(entries, page=current_page, url=page_url,
                items_per_page=items_per_page)
    grid = Grid([entry.__json__() for entry in page],
                context.__model__.grid_columns())
    return {'caption': context.__model__.__name__ + 's',
            'grid': grid, 'page': page}


## 404

def notfound_view(context, request):
    request.response_status = 404
    return dict()

## Widgets


def view_widget(context, request):
    context.fetch_data(request)
    mw = tw2.core.core.request_local()['middleware']
    mw.controllers.register(context, 'update_submit')
    return {'widget': context}


@view_config(route_name='home', renderer='bodhi:templates/home.mak')
def home(request):
    return {}


def save(request):
    print request.params

    # Validate the CSRF token
    #token = request.session.get_csrf_token()
    #if token != request.POST['csrf_token']:
    #    raise ValueError('CSRF token did not match')

    # Validate parameters
    try:
        data = NewUpdateForm.validate(request.POST)
    except tw2.core.ValidationError, e:
        return Response(e.widget.display())

    pprint(data)
    session = DBSession()

    # Make sure submitter has commit access
    # Editing magic
    # Create model instances
    # Obsolete any older updates, inherit data
    # Bugzilla interactions
    # Security checks
    # Look for unit tests
    # Send out email notifications
    # Set request, w/ critpath checks

    return Response("Hi There!")


@cache_region('long_term', 'package_list')
def get_all_packages():
    """ Get a list of all packages in Koji """
    log.debug('Fetching list of all packages...')
    koji = buildsys.get_session()
    return [pkg['package_name'] for pkg in koji.listPackages()]


def search_pkgs(request):
    """ Called by the NewUpdateForm.builds AutocompleteWidget """
    packages = get_all_packages()
    return [{'id': p, 'label': p, 'value': p} for p in packages
            if request.GET['term'] in p]


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
    login_url = route_url('login', request)
    referrer = request.url
    if referrer == login_url:
        referrer = '/'
    came_from = request.params.get('came_from', referrer)
    request.session['came_from'] = came_from
    return dict(url=request.route_url('verify_openid'))


def logout(request):
    headers = forget(request)
    return HTTPFound(location=request.application_url, headers=headers)


def remember_me(context, request, *args, **kw):
    print(request.params)
    identity = request.params['openid.identity']
    if not identity.startswith(request.registry.settings['openid.provider']):
        request.session.flash('Invalid OpenID provider. You can only use: %s' %
                              request.registry.settings['openid.provider'])
        return HTTPFound(location=request.aplication_url + '/login')
    username = identity.split('/')[-1]
    headers = remember(request, username)
    came_from = request.session['came_from']
    del(request.session['came_from'])
    response = HTTPFound(location=came_from)
    response.headerlist.extend(headers)
    return response
