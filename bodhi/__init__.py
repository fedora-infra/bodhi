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

from bodhi.resources import appmaker
import bodhi.buildsys


def main(global_config, testing=None, **settings):
    """ This function returns a WSGI application """
    engine = engine_from_config(settings, 'sqlalchemy.')
    get_root = appmaker(engine)

    # Setup our buildsystem
    bodhi.buildsys.setup_buildsystem(settings)

    # Beaker Sessions & Caching
    session_factory = session_factory_from_settings(settings)
    set_cache_regions_from_settings(settings)

    config = Configurator(settings=settings, root_factory=get_root,
                          session_factory=session_factory)

    # Authentication & Authorization
    if testing:
        # use a permissive security policy while running unit tests
        config.testing_securitypolicy(userid=testing, permissive=True)
    else:
        config.set_authentication_policy(AuthTktAuthenticationPolicy(
                settings['authtkt.secret']))
        config.set_authorization_policy(ACLAuthorizationPolicy())

    config.add_static_view('static', 'bodhi:static')
    config.add_translation_dirs('bodhi:locale/')

    # Save method
    config.add_route('save', '/save',
                     view='bodhi.views.save',
                     request_method='POST',
                     permission='add')

    config.add_route('latest_candidates', '/latest_candidates',
                     view='bodhi.views.latest_candidates',
                     renderer='json')

    # Auto-completion search
    config.add_route('search_pkgs', '/search_pkgs',
                     view='bodhi.views.search_pkgs',
                     renderer='json', request_method='GET')

    # JSON views
    config.add_view('bodhi.views.view_model_instance_json',
                    context='bodhi.models.Base',
                    accept='application/json',
                    renderer='json')
    config.add_view('bodhi.views.view_model_json',
                    context='bodhi.resources.BodhiResource',
                    accept='application/json',
                    renderer='json')

    # Mako template views
    config.add_view('bodhi.views.view_model_instance',
                    context='bodhi.models.Base',
                    accept='text/html',
                    renderer='bodhi:templates/instance.mak')
    config.add_view('bodhi.views.view_model',
                    accept='text/html',
                    context='bodhi.resources.BodhiResource',
                    renderer='bodhi:templates/model.mak')

    # Widgets
    config.add_view('bodhi.views.view_widget',
                    context='bodhi.widgets.NewUpdateForm',
                    renderer="bodhi:templates/widget.mak",
                    permission='add')

    # 404
    config.add_view('bodhi.views.notfound_view',
                    renderer='bodhi:templates/404.mak',
                    context=NotFound)

    # pyramid.openid
    config.add_route('login', '/login',
                     view='bodhi.views.login',
                     view_renderer='bodhi:templates/login.mak')
    config.add_view('bodhi.views.login', context=Forbidden,
                    renderer='bodhi:templates/login.mak')
    config.add_route('logout', '/logout', view='bodhi.views.logout')
    config.add_route('verify_openid', pattern='/dologin.html',
                     view='pyramid_openid.verify_openid')

    return config.make_wsgi_app()
