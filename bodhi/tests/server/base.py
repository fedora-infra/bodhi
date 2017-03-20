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

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import requests
import transaction

from bodhi.server import bugs, log, models
from bodhi.tests.server import create_update, populate


DB_PATH = 'sqlite://'
DB_NAME = None


FAITOUT = 'http://209.132.184.152/faitout/'
# The BUILD_ID environment variable is set by Jenkins and allows us to detect if
# we are running the tests in jenkins or not
# https://wiki.jenkins-ci.org/display/JENKINS/Building+a+software+project#Buildingasoftwareproject-below
if os.environ.get('BUILD_ID'):
    try:
        req = requests.get('%s/new' % FAITOUT, timeout=60)
        if req.status_code == 200:
            DB_PATH = req.text
            DB_NAME = DB_PATH.rsplit('/', 1)[1]
            print 'Using faitout at: %s' % DB_PATH
    except:
        pass


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        bugs.set_bugtracker()
        engine = create_engine(DB_PATH)
        # We want a special session that lasts longer than a transaction
        self.Session = scoped_session(
            sessionmaker(bind=engine, extension=ZopeTransactionExtension(keep_session=True)))
        log.debug('Creating all models for %s' % engine)
        models.Base.metadata.bind = engine
        models.Base.metadata.create_all(engine)
        self.db = self.Session()
        transaction.begin()
        populate(self.db)

        # Track sql statements in every test
        self.sql_statements = []

        def track(conn, cursor, statement, param, ctx, many):
            self.sql_statements.append(statement)

        event.listen(engine, "before_cursor_execute", track)

    def tearDown(self):
        transaction.abort()
        log.debug('Removing session')
        self.db.close()
        self.Session.remove()
        del self.sql_statements

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
        transaction.begin()
        try:
            yield session
            transaction.commit()
        except:
            transaction.abort()
            raise
        finally:
            session.close()
