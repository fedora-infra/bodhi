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
"""
This module contains a useful base test class that helps with common testing needs when testing
bodhi.server modules.
"""
from contextlib import contextmanager
import os
import unittest

from webtest import TestApp
from sqlalchemy import event
import mock

from bodhi.server import bugs, buildsys, models, initialize_db, Session, config, main
from bodhi.tests.server import create_update, populate


original_config = config.config.copy()
engine = None
_app = None
DEFAULT_DB = 'sqlite:///' + os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../../bodhi-tests.sqlite'))


def _configure_test_db(db_uri=DEFAULT_DB):
    """
    Creates and configures a test database for Bodhi.

    .. note::
        For some reason, this fails on the in-memory version of SQLite with an error
        about nested transactions.

    Args:
        db_uri (str): The URI to use when creating the database engine. Defaults to an
            in-memory SQLite database.
    """
    if db_uri.startswith('sqlite:////'):
        # Clean out any old file
        db_path = db_uri.split('sqlite:///')[1]
        if os.path.isfile(db_path):
            os.unlink(db_path)

    global engine
    engine = initialize_db({'sqlalchemy.url': db_uri})

    if db_uri.startswith('sqlite://'):
        # Necessary to get nested transactions working with SQLite. See:
        # http://docs.sqlalchemy.org/en/latest/dialects/sqlite.html\
        # #serializable-isolation-savepoints-transactional-ddl
        @event.listens_for(engine, "connect")
        def connect_event(dbapi_connection, connection_record):
            """Stop pysqlite from emitting 'BEGIN'"""
            # disable pysqlite's emitting of the BEGIN statement entirely.
            # also stops it from emitting COMMIT before any DDL.
            dbapi_connection.isolation_level = None

        @event.listens_for(engine, "begin")
        def begin_event(conn):
            """Emit our own 'BEGIN' instead of letting pysqlite do it."""
            conn.execute('BEGIN')

    @event.listens_for(Session, 'after_transaction_end')
    def restart_savepoint(session, transaction):
        """Allow tests to call rollback on the session."""
        if transaction.nested and not transaction._parent.nested:
            session.expire_all()
            session.begin_nested()

    return engine


class BaseTestCase(unittest.TestCase):
    """
    The base test class for Bodhi.

    This class configures the global scoped session with a test database.
    The test database makes use of nested transactions to provide a clean
    slate for each test. Tests may call both ``commit`` and ``rollback``
    on the database session they acquire from ``bodhi.server.Session``.
    """
    _populate_db = True

    app_settings = {
        'authtkt.secret': 'sssshhhhhh',
        'authtkt.secure': False,
        'mako.directories': 'bodhi:server/templates',
        'session.type': 'memory',
        'session.key': 'testing',
        'session.secret': 'foo',
        'dogpile.cache.backend': 'dogpile.cache.memory',
        'dogpile.cache.expiration_time': 0,
        'cache.type': 'memory',
        'cache.regions': 'default_term, second, short_term, long_term',
        'cache.second.expire': '1',
        'cache.short_term.expire': '60',
        'cache.default_term.expire': '300',
        'cache.long_term.expire': '3600',
        'acl_system': 'dummy',
        'buildsystem': 'dummy',
        'important_groups': 'proventesters provenpackager releng',
        'admin_groups': 'bodhiadmin releng',
        'admin_packager_groups': 'provenpackager',
        'mandatory_packager_groups': 'packager',
        'critpath_pkgs': 'kernel',
        'critpath.num_admin_approvals': 0,
        'bugtracker': 'dummy',
        'stats_blacklist': 'bodhi autoqa',
        'system_users': 'bodhi autoqa',
        'max_update_length_for_ui': '70',
        'openid.provider': 'https://id.stg.fedoraproject.org/openid/',
        'openid.url': 'https://id.stg.fedoraproject.org',
        'test_case_base_url': 'https://fedoraproject.org/wiki/',
        'openid_template': '{username}.id.fedoraproject.org',
        'site_requirements': u'rpmlint',
        'resultsdb_api_url': 'whatever',
        'base_address': 'http://0.0.0.0:6543',
        'cors_connect_src': 'http://0.0.0.0:6543',
        'cors_origins_ro': 'http://0.0.0.0:6543',
        'cors_origins_rw': 'http://0.0.0.0:6543',
    }

    def setUp(self):
        # Ensure "cached" objects are cleared before each test.
        models.Release._all_releases = None
        models.Release._tag_cache = None

        if engine is None:
            self.engine = _configure_test_db()
        else:
            self.engine = engine

        self.connection = self.engine.connect()
        models.Base.metadata.create_all(bind=self.connection)
        self.transaction = self.connection.begin()

        Session.remove()
        Session.configure(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.Session = Session
        self.db = Session()
        self.db.begin_nested()

        if self._populate_db:
            populate(self.db)

        bugs.set_bugtracker()
        buildsys.setup_buildsystem({'buildsystem': 'dev'})

        def request_db(request=None):
            """
            Replace the db session function with one that doesn't close the session.

            This allows tests to make assertions about the database. Without it, all
            the changes would be rolled back to when the nested transaction is started.
            """
            def cleanup(request):
                if request.exception is not None:
                    Session().rollback()
                else:
                    Session().commit()
            request.add_finished_callback(cleanup)
            return Session()
        self._request_sesh = mock.patch('bodhi.server.get_db_session_for_request', request_db)
        self._request_sesh.start()

        # Create the test WSGI app one time. We should avoid creating too many
        # of these since Pyramid holds global references to the objects it creates
        # and this results in a substantial memory leak. Long term we should figure
        # out how to make Pyramid forget about these.
        global _app
        if _app is None:
            _app = TestApp(main({}, testing=u'guest', **self.app_settings))
        self.app = _app

    def get_csrf_token(self):
        return self.app.get('/csrf').json_body['csrf_token']

    def get_update(self, builds='bodhi-2.0-1.fc17', stable_karma=3, unstable_karma=-3):
        if isinstance(builds, list):
            builds = ','.join(builds)
        if not isinstance(builds, str):
            builds = builds.encode('utf-8')
        return {
            'builds': builds,
            'bugs': u'',
            'notes': u'this is a test update',
            'type': u'bugfix',
            'autokarma': True,
            'stable_karma': stable_karma,
            'unstable_karma': unstable_karma,
            'requirements': u'rpmlint',
            'require_bugs': False,
            'require_testcases': True,
            'csrf_token': self.get_csrf_token(),
        }

    def tearDown(self):
        """Roll back all the changes from the test and clean up the session."""
        self._request_sesh.stop()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()
        Session.remove()

    def create_update(self, build_nvrs, release_name=u'F17'):
        """
        Create and return an Update with the given iterable of build_nvrs. Each build_nvr should be
        a tuple of strings describing the name, version, and release for the build. For example,
        build_nvrs might look like this:

        ((u'bodhi', u'2.3.3', u'1.fc24'), (u'python-fedora-atomic-composer', u'2016.3', u'1.fc24'))

        You can optionally pass a release_name to select a different release than the default F17,
        but the release must already exist in the database.

        This is a convenience wrapper around bodhi.tests.server.create_update so that tests can just
        call self.create_update() and not have to pass self.db.
        """
        return create_update(self.db, build_nvrs, release_name)


class TransactionalSessionMaker(object):
    """
    Mimic the behavior of bodhi.server.utils.TransactionalSessionMaker, but allow tests to inject
    the test database Session.
    """
    def __init__(self, Session):
        """
        Store the Session for later retrieval.
        """
        self._Session = Session

    @contextmanager
    def __call__(self):
        session = self._Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
