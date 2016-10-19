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

import unittest

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

from bodhi.server import log
from bodhi.tests.server import populate
from bodhi.server.models import (
    Base,
)

DB_PATH = 'sqlite://'
DB_NAME = None


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        engine = create_engine(DB_PATH)
        # We want a special session that lasts longer than a transaction
        Session = scoped_session(
            sessionmaker(bind=engine, extension=ZopeTransactionExtension(keep_session=True)))
        log.debug('Creating all models for %s' % engine)
        Base.metadata.bind = engine
        Base.metadata.create_all(engine)
        self.db = Session()
        populate(self.db)

        # Track sql statements in every test
        self.sql_statements = []

        def track(conn, cursor, statement, param, ctx, many):
            self.sql_statements.append(statement)

        event.listen(engine, "before_cursor_execute", track)

    def tearDown(self):
        log.debug('Removing session')
        self.db.close()
        del self.sql_statements
