from collections import defaultdict
from dogpile.cache import make_region
from sqlalchemy import engine_from_config

from pyramid.settings import asbool
from pyramid.decorator import reify
from pyramid.security import unauthenticated_userid
from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from fedora.client.pkgdb import PackageDB

from . import buildsys

import logging

log = logging.getLogger(__name__)


#
# Request methods
#

def get_dbsession(request):
    from bodhi.models import DBSession
    return DBSession()


def get_cacheregion(request):
    region = make_region()
    region.configure_from_config(request.registry.settings, "dogpile.cache.")
    return region


def get_user(request):
    from bodhi.models import User
    userid = unauthenticated_userid(request)
    if userid is not None:
        return request.db.query(User).filter_by(name=unicode(userid)).one()


def groupfinder(userid, request):
    user = request.user
    if user:
        return ['group:' + group.name for group in user.groups]


def get_koji(request):
    return buildsys.get_session()


def get_pkgdb(request):
    return PackageDB(request.registry.settings['pkgdb_url'])


def get_buildinfo(request):
    """
    A per-request cache populated by the validators and shared with the views
    to store frequently used package-specific data, like build tags and ACLs.
    """
    return defaultdict(dict)

#
# Bodhi initialization
#

def main(global_config, testing=None, **settings):
    """ This function returns a WSGI application """
    from bodhi.models import DBSession, Base
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    # Setup our buildsystem
    buildsys.setup_buildsystem(settings)

    # Sessions & Caching
    from pyramid.session import SignedCookieSessionFactory
    session_factory = SignedCookieSessionFactory(settings['session.secret'])

    config = Configurator(settings=settings,
                          session_factory=session_factory)

    # Plugins
    config.include('pyramid_mako')
    config.include('cornice')

    # Lazy-loaded memoized request properties
    config.add_request_method(get_user, 'user', reify=True)
    config.add_request_method(get_koji, 'koji', reify=True)
    config.add_request_method(get_pkgdb, 'pkgdb', reify=True)
    config.add_request_method(get_dbsession, 'db', reify=True)
    config.add_request_method(get_cacheregion, 'cache', reify=True)
    config.add_request_method(get_buildinfo, 'buildinfo', reify=True)

    # Templating
    config.add_mako_renderer('.html', settings_prefix='mako.')
    config.add_static_view('static', 'bodhi:static')

    # i18n
    config.add_translation_dirs('bodhi:locale/')

    # Authentication & Authorization
    if testing:
        # use a permissive security policy while running unit tests
        config.testing_securitypolicy(userid=testing, permissive=True)
    else:
        config.set_authentication_policy(AuthTktAuthenticationPolicy(
                settings['authtkt.secret'],
                callback=groupfinder,
                secure=asbool(settings['authtkt.secure']),
                hashalg='sha512'))
        config.set_authorization_policy(ACLAuthorizationPolicy())

    # Frontpage
    config.add_route('home', '/')

    # Metrics
    config.add_route('metrics', '/metrics')

    # Utils
    config.add_route('markdowner', '/markdown')

    # Auto-completion search
    config.add_route('search_pkgs', '/search_pkgs')
    config.add_route('latest_candidates', '/latest_candidates')

    # pyramid.openid
    config.add_route('login', '/login')
    config.add_view('bodhi.security.login', route_name='login')
    #config.add_view('bodhi.views.login', context=Forbidden,
    #                renderer='bodhi:templates/login.mak')
    config.add_route('logout', '/logout')
    config.add_view('bodhi.security.logout', route_name='logout')
    config.add_route('verify_openid', pattern='/dologin.html')
    config.add_view('pyramid_fas_openid.verify_openid', route_name='verify_openid')

    config.scan('bodhi.views')
    config.scan('bodhi.services')

    return config.make_wsgi_app()
