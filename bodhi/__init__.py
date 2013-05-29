from sqlalchemy import engine_from_config

from pyramid.exceptions import NotFound, Forbidden
from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid
from pyramid.config import Configurator
from pyramid_beaker import session_factory_from_settings
from pyramid_beaker import set_cache_regions_from_settings
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy

import bodhi.buildsys
from .models import DBSession, Base, User
from .resources import appmaker


def get_user(request):
    userid = unauthenticated_userid(request)
    if userid is not None:
        session = DBSession()
        return session.query(User).filter_by(name=userid).one()


def groupfinder(userid, request):
    user = request.user
    if user:
        return [group.name for group in user.groups]


def main(global_config, testing=None, **settings):
    """ This function returns a WSGI application """
    engine = engine_from_config(settings, 'sqlalchemy.')
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    get_root = appmaker(engine)

    # Setup our buildsystem
    bodhi.buildsys.setup_buildsystem(settings)

    # Beaker Sessions & Caching
    session_factory = session_factory_from_settings(settings)
    set_cache_regions_from_settings(settings)

    config = Configurator(settings=settings, root_factory=get_root,
                          session_factory=session_factory)

    config.add_request_method(get_user, 'user', reify=True)
    config.add_static_view('static', 'bodhi:static')
    config.add_translation_dirs('bodhi:locale/')
    config.add_renderer(".html", "pyramid.mako_templating.renderer_factory")

    # Authentication & Authorization
    if testing:
        # use a permissive security policy while running unit tests
        config.testing_securitypolicy(userid=testing, permissive=True)
    else:
        config.set_authentication_policy(AuthTktAuthenticationPolicy(
                settings['authtkt.secret'],
                callback=groupfinder))
        config.set_authorization_policy(ACLAuthorizationPolicy())

    # Frontpage
    config.add_route('home', '/')

    # Save method
    config.add_route('save', '/save')

    # Auto-completion search
    config.add_route('search_pkgs', '/search_pkgs')
    config.add_route('latest_candidates', '/latest_candidates')

    # pyramid.openid
    config.add_route('login', '/login', view='bodhi.views.login')
    #config.add_view('bodhi.views.login', context=Forbidden,
    #                renderer='bodhi:templates/login.mak')
    config.add_route('logout', '/logout', view='bodhi.views.logout')
    config.add_route('verify_openid', pattern='/dologin.html',
                     view='pyramid_fas_openid.verify_openid')

    config.scan()


    return config.make_wsgi_app()
