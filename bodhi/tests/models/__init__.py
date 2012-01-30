# -*- coding: utf-8 -*-
"""Unit test suite for the models of the application."""

import json

from nose.tools import assert_equals, eq_

from bodhi.models import DBSession
from bodhi.tests import setup_db, teardown_db


def setup():
    """Function called by nose on module load"""
    # Doesn't appear to be necessary as long as our functional test suite
    # runs first (which sets up the DBSession)
    #setup_db()


def teardown():
    """Function called by nose after all tests in this module ran"""
    teardown_db()


class ModelTest(object):
    """Base unit test case for the models."""

    klass = None
    attrs = {}

    def setup(self):
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
        DBSession.rollback()

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
