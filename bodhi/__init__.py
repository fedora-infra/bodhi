from collections import defaultdict
from sqlalchemy import engine_from_config

from pyramid.settings import asbool
from pyramid.decorator import reify
from pyramid.security import unauthenticated_userid
from pyramid.config import Configurator
from pyramid_beaker import session_factory_from_settings
from pyramid_beaker import set_cache_regions_from_settings
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

from fedora.client.pkgdb import PackageDB

from . import buildsys
from .models import DBSession, Base, User

import logging

log = logging.getLogger(__name__)


#
# Request methods
#

def get_dbsession(request):
    return DBSession()


def get_user(request):
    userid = unauthenticated_userid(request)
    if userid is not None:
        return request.db.query(User).filter_by(name=userid).one()


def groupfinder(userid, request):
    user = request.user
    if user:
        return [group.name for group in user.groups]


def get_koji(request):
    return buildsys.get_session()


def get_pkgdb(request):
    return PackageDB(request.registry.settings['pkgdb_url'])


def get_buildinfo(request):
    return defaultdict(dict)


#
# Bodhi initialization
#

def main(global_config, testing=None, **settings):
    """ This function returns a WSGI application """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    # Setup our buildsystem
    buildsys.setup_buildsystem(settings)

    # Beaker Sessions & Caching
    session_factory = session_factory_from_settings(settings)
    set_cache_regions_from_settings(settings)

    config = Configurator(settings=settings,
                          session_factory=session_factory)

    # Plugins
    config.include('cornice')

    # Lazy-loaded memoized request properties
    config.add_request_method(get_user, 'user', reify=True)
    config.add_request_method(get_koji, 'koji', reify=True)
    config.add_request_method(get_pkgdb, 'pkgdb', reify=True)
    config.add_request_method(get_dbsession, 'db', reify=True)
    config.add_request_method(get_buildinfo, 'buildinfo', reify=True)

    # Templating
    config.add_renderer(".html", "pyramid.mako_templating.renderer_factory")
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

    # Auto-completion search
    config.add_route('search_pkgs', '/search_pkgs')
    config.add_route('latest_candidates', '/latest_candidates')

    # pyramid.openid
    config.add_route('login', '/login', view='bodhi.security.login')
    #config.add_view('bodhi.views.login', context=Forbidden,
    #                renderer='bodhi:templates/login.mak')
    config.add_route('logout', '/logout', view='bodhi.security.logout')
    config.add_route('verify_openid', pattern='/dologin.html',
                     view='pyramid_fas_openid.verify_openid')

    config.scan('bodhi.views')

    return config.make_wsgi_app()
