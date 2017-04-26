# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from collections import defaultdict
import logging

from cornice.validators import DEFAULT_FILTERS
from dogpile.cache import make_region
from munch import munchify
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid.config import Configurator
from pyramid.exceptions import HTTPForbidden
from pyramid.renderers import JSONP
from pyramid.security import unauthenticated_userid
from pyramid.settings import asbool
from sqlalchemy import engine_from_config, event
from sqlalchemy.orm import scoped_session, sessionmaker

from bodhi.server import bugs, buildsys, ffmarkdown


log = logging.getLogger(__name__)


# TODO -- someday move this externally to "fedora_flavored_markdown"
ffmarkdown.inject()


#
# Request methods
#

def get_db_session_for_request(request=None):
    """
    This function returns a database session that is meant to be used for the given request.

    It handles rolling back or committing the session based on whether an exception occurred or
    not. To get a database session that's not tied to the request/response cycle, just use the
    :data:`Session` scoped session in this module.

    Args:
        request (pyramid.request): The request object to create a session for.

    Returns:
        sqlalchemy.orm.session.Session: A database session.
    """
    session = request.registry.sessionmaker()

    def cleanup(request):
        """A post-request hook that commits the database changes if no exceptions occurred."""
        if request.exception is not None:
            session.rollback()
        else:
            session.commit()
        session.close()

    request.add_finished_callback(cleanup)

    return session


def get_cacheregion(request):
    region = make_region()
    region.configure_from_config(request.registry.settings, "dogpile.cache.")
    return region


def get_user(request):
    from bodhi.server.models import User
    userid = unauthenticated_userid(request)
    if userid is not None:
        user = request.db.query(User).filter_by(name=unicode(userid)).first()
        # Why munch?  https://github.com/fedora-infra/bodhi/issues/473
        return munchify(user.__json__(request=request))


def groupfinder(userid, request):
    from bodhi.server.models import User
    if request.user:
        user = User.get(request.user.name, request.db)
        return ['group:' + group.name for group in user.groups]


def get_koji(request):
    return buildsys.get_session()


def get_buildinfo(request):
    """
    A per-request cache populated by the validators and shared with the views
    to store frequently used package-specific data, like build tags and ACLs.
    """
    return defaultdict(dict)


def get_releases(request):
    from bodhi.server.models import Release
    return Release.all_releases(request.db)


#
# Cornice filters
#

def exception_filter(response, request):
    """Log exceptions that get thrown up to cornice"""
    if isinstance(response, Exception):
        log.exception('Unhandled exception raised:  %r' % response)
    return response

DEFAULT_FILTERS.insert(0, exception_filter)


#
# Bodhi initialization
#

#: An SQLAlchemy scoped session with an engine configured using the settings in Bodhi's server
#: configuration file. Note that you *must* call :func:`initialize_db` before you can use this.
Session = scoped_session(sessionmaker())


def initialize_db(config):
    """
    Initialize the database using the given configuration.

    This *must* be called before you can use the :data:`Session` object.

    Args:
        config (dict): The Bodhi server configuration dictionary.

    Returns:
        sqlalchemy.engine: The database engine created from the configuration.
    """
    # The SQLAlchemy database engine. This is constructed using the value of
    # ``DB_URL`` in :data:`config``. Note: A copy is provided since ``engine_from_config``
    # uses ``pop``.
    engine = engine_from_config(config.copy(), 'sqlalchemy.')
    # When using SQLite we need to make sure foreign keys are enabled:
    # http://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support
    if config['sqlalchemy.url'].startswith('sqlite:'):
        event.listen(
            engine,
            'connect',
            lambda db_con, con_record: db_con.execute('PRAGMA foreign_keys=ON')
        )
    Session.configure(bind=engine)
    return engine


def main(global_config, testing=None, session=None, **settings):
    """ This function returns a WSGI application """
    # Setup our bugtracker and buildsystem
    bugs.set_bugtracker()
    buildsys.setup_buildsystem(settings)

    # Sessions & Caching
    from pyramid.session import SignedCookieSessionFactory
    session_factory = SignedCookieSessionFactory(settings['session.secret'])

    # Construct a list of all groups we're interested in
    default = ' '.join([settings.get(key, '') for key in [
        'important_groups',
        'admin_packager_groups',
        'mandatory_packager_groups',
        'admin_groups',
    ]])
    # pyramid_fas_openid looks for this setting
    settings['openid.groups'] = settings.get('openid.groups', default).split()

    config = Configurator(settings=settings, session_factory=session_factory)

    # Plugins
    config.include('pyramid_mako')
    config.include('cornice')

    # Initialize the database scoped session
    initialize_db(settings)

    # Lazy-loaded memoized request properties
    if session:
        config.registry.sessionmaker = lambda: session
    else:
        config.registry.sessionmaker = Session

    config.add_request_method(get_db_session_for_request, 'db', reify=True)

    config.add_request_method(get_user, 'user', reify=True)
    config.add_request_method(get_koji, 'koji', reify=True)
    config.add_request_method(get_cacheregion, 'cache', reify=True)
    config.add_request_method(get_buildinfo, 'buildinfo', reify=True)
    config.add_request_method(get_releases, 'releases', reify=True)

    # Templating
    config.add_mako_renderer('.html', settings_prefix='mako.')
    config.add_static_view('static', 'bodhi:server/static')

    from bodhi.server.renderers import rss, jpeg
    config.add_renderer('rss', rss)
    config.add_renderer('jpeg', jpeg)
    config.add_renderer('jsonp', JSONP(param_name='callback'))

    # i18n
    config.add_translation_dirs('bodhi:server/locale/')

    # Authentication & Authorization
    if testing:
        # use a permissive security policy while running unit tests
        config.testing_securitypolicy(userid=testing, permissive=True)
    else:
        timeout = int(settings.get('authtkt.timeout', '86400'))
        config.set_authentication_policy(AuthTktAuthenticationPolicy(
            settings['authtkt.secret'], callback=groupfinder,
            secure=asbool(settings['authtkt.secure']), hashalg='sha512', timeout=timeout,
            max_age=timeout))
        config.set_authorization_policy(ACLAuthorizationPolicy())

    # Frontpage
    config.add_route('home', '/')

    # Views for creating new objects
    config.add_route('new_update', '/updates/new')
    config.add_route('new_override', '/overrides/new')
    config.add_route('new_stack', '/stacks/new')

    # Metrics
    config.add_route('metrics', '/metrics')
    config.add_route('masher_status', '/masher/')

    # Auto-completion search
    config.add_route('search_packages', '/search/packages')
    config.add_route('latest_candidates', '/latest_candidates')
    config.add_route('latest_builds', '/latest_builds')

    config.add_route('captcha_image', '/captcha/{cipherkey}/')

    # pyramid.openid
    config.add_route('login', '/login')
    config.add_view('bodhi.server.security.login', route_name='login')
    config.add_view('bodhi.server.security.login', context=HTTPForbidden)
    config.add_route('logout', '/logout')
    config.add_view('bodhi.server.security.logout', route_name='logout')
    config.add_route('verify_openid', pattern='/dologin.html')
    config.add_view('pyramid_fas_openid.verify_openid', route_name='verify_openid')

    config.add_route('api_version', '/api_version')

    # The only user preference we have.
    config.add_route('popup_toggle', '/popup_toggle')

    config.scan('bodhi.server.views')
    config.scan('bodhi.server.services')
    config.scan('bodhi.server.captcha')

    return config.make_wsgi_app()
