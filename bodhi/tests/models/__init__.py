# -*- coding: utf-8 -*-

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

"""Unit test suite for the models of the application."""

import json

from nose.tools import assert_equals, eq_
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

from bodhi.models import Base


class ModelTest(object):
    """Base unit test case for the models."""

    klass = None
    attrs = {}

    def setup(self):
        engine = create_engine('sqlite://')
        Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
        Session.configure(bind=engine)
        self.db = Session()
        Base.metadata.create_all(engine)
        try:
            new_attrs = {}
            new_attrs.update(self.attrs)
            new_attrs.update(self.do_get_dependencies())
            self.obj = self.klass(**new_attrs)
            self.db.add(self.obj)
            self.db.flush()
            return self.obj
        except:
            self.db.rollback()
            raise

    def tearDown(self):
        self.db.close()

    def do_get_dependencies(self):
        """ Use this method to pull in other objects that need to be
        created for this object to be built properly.
        """

        return {}

    def test_create_obj(self):
        pass

    def test_query_obj(self):
        for key, value in self.attrs.iteritems():
            assert_equals(getattr(self.obj, key), value)

    def test_json(self):
        """ Ensure our models can return valid JSON """
        assert json.dumps(self.obj.__json__())

    def test_get(self):
        for col in self.obj.__get_by__:
            eq_(self.klass.get(getattr(self.obj, col), self.db), self.obj)
