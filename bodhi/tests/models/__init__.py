# -*- coding: utf-8 -*-
"""Unit test suite for the models of the application."""

import json

from nose.tools import assert_equals, eq_
from sqlalchemy import create_engine

from bodhi.models import DBSession, Base


class ModelTest(object):
    """Base unit test case for the models."""

    klass = None
    attrs = {}

    def setup(self):
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        try:
            new_attrs = {}
            new_attrs.update(self.attrs)
            new_attrs.update(self.do_get_dependencies())
            self.obj = self.klass(**new_attrs)
            DBSession.add(self.obj)
            DBSession.flush()
            return self.obj
        except:
            DBSession.rollback()
            raise

    def tearDown(self):
        DBSession.remove()

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
            eq_(self.klass.get(getattr(self.obj, col), DBSession), self.obj)
