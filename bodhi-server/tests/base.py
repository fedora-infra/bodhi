# Copyright © 2016-2019 Red Hat, Inc.
#
# This file is part of Bodhi.
#
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
"""Contains a useful base test class that helps with common testing needs for bodhi.server."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest import mock
import os
import subprocess
import unittest

from pyramid import testing
from pyramid.paster import get_appsettings
from sqlalchemy import event
from sqlalchemy.orm.exc import NoResultFound
from webtest import TestApp
import createrepo_c

from bodhi.server import (
    bugs,
    buildsys,
    config,
    initialize_db,
    main,
    metadata,
    models,
    Session,
    webapp,
)


original_config = config.config.copy()
engine = None
_app = None
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))


def _configure_test_db(db_uri):
    """
    Create and configure a test database for Bodhi.

    .. note::
        For some reason, this fails on the in-memory version of SQLite with an error
        about nested transactions.

    Args:
        db_uri (str): The URI to use when creating the database engine. Defaults to an
            in-memory SQLite database.
    Returns:
        sqlalchemy.engine: The database engine.
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
            """Stop pysqlite from emitting 'BEGIN'."""
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


def create_update(session, build_nvrs, release_name='F17'):
    """
    Use the given session to create and return an Update with the given iterable of build_nvrs.

    Each build_nvr should be a string describing the name, version, and release for the build
    separated by dashes. For example, build_nvrs might look like this:

    ('bodhi-2.3.3-1.fc24', 'python-fedora-atomic-composer-2016.3-1.fc24')

    You can optionally pass a release_name to select a different release than the default F17, but
    the release must already exist in the database.

    Args:
        build_nvrs (iterable): An iterable of strings of NVRs to put into the update.
        release_name (str): The name of the release to associate with the update.
    Returns:
        bodhi.server.models.Update: The generated update.
    """
    release = session.query(models.Release).filter_by(name=release_name).one()
    user = session.query(models.User).filter_by(name='guest').one()

    builds = []
    for nvr in build_nvrs:
        name, version, rel = nvr.rsplit('-', 2)
        try:
            package = session.query(models.RpmPackage).filter_by(name=name).one()
        except NoResultFound:
            package = models.RpmPackage(name=name)
            session.add(package)

        try:
            testcase = session.query(models.TestCase).filter_by(name='Wat').one()
        except NoResultFound:
            testcase = models.TestCase(name='Wat')
            session.add(testcase)

        build = models.RpmBuild(nvr=nvr, release=release, package=package, signed=True)
        build.testcases.append(testcase)
        builds.append(build)
        session.add(build)

        # Add a buildroot override for this build
        expiration_date = datetime.utcnow()
        expiration_date = expiration_date + timedelta(days=1)
        override = models.BuildrootOverride(build=build, submitter=user,
                                            notes='blah blah blah',
                                            expiration_date=expiration_date)
        session.add(override)

    update = models.Update(
        builds=builds, user=user, request=models.UpdateRequest.testing,
        notes='Useful details!', type=models.UpdateType.bugfix,
        date_submitted=datetime(1984, 11, 2),
        requirements='rpmlint', stable_karma=3, unstable_karma=-3, release=release)
    session.add(update)
    return update


def populate(db):
    """
    Create some data for tests to use.

    Args:
        db (sqlalchemy.orm.session.Session): The database session.
    """
    user = models.User(name='guest')
    db.add(user)
    anonymous = models.User(name='anonymous')
    db.add(anonymous)
    provenpackager = models.Group(name='provenpackager')
    db.add(provenpackager)
    packager = models.Group(name='packager')
    db.add(packager)
    user.groups.append(packager)
    release = models.Release(
        name='F17', long_name='Fedora 17',
        id_prefix='FEDORA', version='17',
        dist_tag='f17', stable_tag='f17-updates',
        testing_tag='f17-updates-testing',
        candidate_tag='f17-updates-candidate',
        pending_signing_tag='f17-updates-signing-pending',
        pending_testing_tag='f17-updates-testing-pending',
        pending_stable_tag='f17-updates-pending',
        override_tag='f17-override',
        branch='f17', state=models.ReleaseState.current,
        create_automatic_updates=True,
        package_manager=models.PackageManager.unspecified, testing_repository=None)
    db.add(release)
    db.flush()
    # This mock will help us generate a consistent update alias.
    with mock.patch(target='uuid.uuid4', return_value='wat'):
        update = create_update(db, ['bodhi-2.0-1.fc17'])
    update.type = models.UpdateType.bugfix
    update.severity = models.UpdateSeverity.medium
    bug = models.Bug(bug_id=12345)
    db.add(bug)
    update.bugs.append(bug)

    comment = models.Comment(karma=1, text="wow. amaze.")
    db.add(comment)
    comment.user = user
    update.comments.append(comment)

    comment = models.Comment(karma=0, text="srsly.  pretty good.")
    comment.user = anonymous
    db.add(comment)
    update.comments.append(comment)

    db.add(update)

    db.commit()


class BaseTestCaseMixin:
    """
    The base test class for Bodhi.

    This class configures the global scoped session with a test database before
    calling test methods. The test database makes use of nested transactions to
    provide a clean slate for each test. Tests may call both ``commit`` and
    ``rollback`` on the database session they acquire from
    ``bodhi.server.Session``.
    """

    _populate_db = True

    def _setup_method(self):
        """Set up Bodhi for testing."""
        self.config = testing.setUp()
        self.app_settings = get_appsettings(os.environ["BODHI_CONFIG"])
        config.config.clear()
        config.config.load_config(self.app_settings)

        # Ensure "cached" objects are cleared before each test.
        models.Release.clear_all_releases_cache()
        models.Release._tag_cache = None

        if engine is None:
            self.engine = _configure_test_db(config.config["sqlalchemy.url"])
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

        self._request_sesh = mock.patch('bodhi.server.webapp._complete_database_session',
                                        webapp._rollback_or_commit)
        self._request_sesh.start()

        # Create the test WSGI app one time. We should avoid creating too many
        # of these since Pyramid holds global references to the objects it creates
        # and this results in a substantial memory leak. Long term we should figure
        # out how to make Pyramid forget about these.
        global _app
        if _app is None:
            # We don't want to call Session.remove() during the unit tests, because that will
            # trigger the restart_savepoint() callback defined above which will remove the data
            # added by populate().
            with mock.patch('bodhi.server.Session.remove'):
                _app = TestApp(main({}, testing='guest', session=self.db, **self.app_settings))
        self.app = _app
        self.registry = self.app.app.registry

        # ensure a clean state of the dev build system
        buildsys.DevBuildsys.clear()

    def get_csrf_token(self, app=None):
        """
        Return a CSRF token that can be used by tests as they test the REST API.

        Args:
            app (TestApp): The app to use to get the token. Defaults to None, which will use
                self.app.
        Returns:
            str: A CSRF token.
        """
        if not app:
            app = self.app
        return app.get('/csrf', headers={'Accept': 'application/json'}).json_body['csrf_token']

    def get_update(self, builds='bodhi-2.0-1.fc17', from_tag=None,
                   stable_karma=3, unstable_karma=-3):
        """
        Return a dict describing an update.

        This is useful for tests that want to POST to the API to create an update.

        Args:
            builds (str): A comma-separated list of NVRs to include in the update.
            from_tag (str): A tag from which to fill the list of builds.
            stable_karma (int): The stable karma threshold to use on the update.
            unstable_karma (int): The unstable karma threshold to use on the update.
        """
        update = {
            'bugs': '',
            'notes': 'this is a test update',
            'type': 'bugfix',
            'autokarma': True,
            'stable_karma': stable_karma,
            'unstable_karma': unstable_karma,
            'requirements': 'rpmlint',
            'require_bugs': False,
            'require_testcases': True,
            'csrf_token': self.get_csrf_token(),
        }

        if builds:
            if isinstance(builds, list):
                builds = ','.join(builds)
            if not isinstance(builds, str):
                builds = builds.encode('utf-8')
            update['builds'] = builds

        if from_tag:
            update['from_tag'] = from_tag

        return update

    def _teardown_method(self):
        """Roll back all the changes from the test and clean up the session."""
        self._request_sesh.stop()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()
        Session.remove()
        testing.tearDown()

    def create_update(self, build_nvrs, release_name='F17'):
        """
        Create and return an Update with the given iterable of build_nvrs.

        Each build_nvr should be a string describing the name, version, and release for the build
        separated by dashes. For example, build_nvrs might look like this:

        ('bodhi-2.3.3-1.fc24', 'python-fedora-atomic-composer-2016.3-1.fc24')

        You can optionally pass a release_name to select a different release than the default F17,
        but the release must already exist in the database.

        This is a convenience wrapper around create_update so that tests can just
        call self.create_update() and not have to pass self.db.

        Args:
            build_nvrs (iterable): An iterable of 3-tuples. Each 3-tuple is strings that express
                the name, version, and release of the desired build.
            release_name (str): The name of the release to associate with the new updates.
        Returns:
            bodhi.server.models.Update: The new update.
        """
        return create_update(self.db, build_nvrs, release_name)

    def create_release(self, version, create_automatic_updates=False):
        """
        Create and return a :class:`Release` with the given version.

        Args:
            version (str): A string of the version of the release, such as 27.
        Returns:
            bodhi.server.models.Release: A new release.
        """
        release = models.Release(
            name='F{}'.format(version), long_name='Fedora {}'.format(version),
            id_prefix='FEDORA', version='{}'.format(version.replace('M', '')),
            dist_tag='f{}'.format(version), stable_tag='f{}-updates'.format(version),
            testing_tag='f{}-updates-testing'.format(version),
            candidate_tag='f{}-updates-candidate'.format(version),
            pending_signing_tag='f{}-updates-testing-signing'.format(version),
            pending_testing_tag='f{}-updates-testing-pending'.format(version),
            pending_stable_tag='f{}-updates-pending'.format(version),
            override_tag='f{}-override'.format(version),
            branch='f{}'.format(version), state=models.ReleaseState.current,
            create_automatic_updates=create_automatic_updates,
            package_manager=models.PackageManager.unspecified,
            testing_repository=None)
        self.db.add(release)
        models.Release.clear_all_releases_cache()
        models.Release._tag_cache = None
        self.db.flush()
        return release


class BasePyTestCase(BaseTestCaseMixin):
    """Wraps BaseTestCaseMixin for pytest users.

    {}
    """.format(BaseTestCaseMixin.__doc__)

    def setup_method(self, method):
        """Set up Bodhi for testing."""
        return self._setup_method()

    def teardown_method(self, method):
        """Roll back all the changes from the test and clean up the session."""
        return self._teardown_method()


class BaseTestCase(unittest.TestCase, BaseTestCaseMixin):
    """Wrap BaseTestCaseMixin for old-style unittest.TestCase users.

    Don't derive new tests from this.

    {}
    """.format(BaseTestCaseMixin.__doc__)

    def setUp(self):
        """Dispatch to BasePyTestCase.setup_method()."""
        return self._setup_method()

    def tearDown(self):
        """Dispatch to BasePyTestCase.teardown_method()."""
        return self._teardown_method()


class DummyUser(object):
    """
    A fake user, suitable for passing to pyramid.testing.DummyRequest.

    If you want to fake a Pyramid Request as being made by a particular user, you can instantiate
    one of these bad boys and pass it like this::

        request = pyramid.testing.DummyRequest(user=DummyUser('bowlofeggs'))

    Attributes:
        name (str): The name of the user. Defaults to 'guest'.
    """

    def __init__(self, name='guest'):
        """
        Set the name attribute.

        Args:
            name (str): The user name.
        """
        self.name = name


class TransactionalSessionMaker(object):
    """
    Mimic the behavior of bodhi.server.utils.TransactionalSessionMaker.

    This allows tests to inject the test database Session.
    """

    def __init__(self, Session):
        """
        Store the Session for later retrieval.

        Args:
            Session (sqlalchemy.orm.scoping.scoped_session): A Session class that can be used to
                create a session.
        """
        self._Session = Session

    @contextmanager
    def __call__(self):
        """
        Enter and exit the context, committing or rolling back the transaction as appropriate.

        Yields:
            sqlalchemy.orm.session.Session: A database session.
        """
        session = self._Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def mkmetadatadir(path, updateinfo=None, comps=None, source=False):
    """
    Generate package metadata for a given directory.

    If the metadata doesn't exist, then create it.

    Args:
        path (str): The directory to generate metadata for.
        updateinfo (str or None or bool): The updateinfo to insert instead of example.
            No updateinfo is inserted if False is passed. Passing True provides undefined
            behavior.
        comps (str or None): The comps to insert instead of example.
        source (True): If True, do not insert comps or prestodelta. Defaults to False.
    """
    compsfile = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE comps PUBLIC "-//Red Hat, Inc.//DTD Comps info//EN" "comps.dtd">
<comps>
  <group>
    <id>testable</id>
    <_name>Testable</_name>
    <_description>comps group for testing</_description>
    <packagelist>
      <packagereq>testpkg</packagereq>
    </packagelist>
  </group>
</comps>'''
    updateinfofile = 'something<id>someID</id>something'
    if not os.path.isdir(path):
        os.makedirs(path)
    if not comps and not source:
        comps = os.path.join(path, 'comps.xml')
        with open(comps, 'w') as f:
            f.write(compsfile)
    if updateinfo is None:
        updateinfo = os.path.join(path, 'updateinfo.xml')
        with open(updateinfo, 'w') as f:
            f.write(updateinfofile)

    createrepo_command = ['createrepo_c', '--xz', '--database', '--quiet', path]

    if not source:
        for arg in ('--deltas', 'comps.xml', '--groupfile'):
            createrepo_command.insert(1, arg)

    subprocess.check_call(createrepo_command)
    if updateinfo is not False:
        metadata.insert_in_repo(createrepo_c.XZ, os.path.join(path, 'repodata'), 'updateinfo',
                                'xml', os.path.join(path, 'updateinfo.xml'), True)
