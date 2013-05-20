import unittest
import transaction

from pyramid import testing
from sqlalchemy import create_engine

from bodhi.models import (
    Base, DBSession, Release, Update, User, Package
)
from bodhi.tests import populate


class TestViews(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        populate()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_model_instance_json(self):
        from bodhi.views import view_model_instance_json
        request = testing.DummyRequest()
        context = DBSession.query(Release).first()
        info = view_model_instance_json(context, request)
        self.assertEqual(info['context'], context.__json__())

    def test_view_model_json(self):
        from bodhi.resources import ReleaseResource
        from bodhi.views import view_model_json
        request = testing.DummyRequest()
        info = view_model_json(ReleaseResource, request)
        self.assertEqual(len(info['entries']), 1)

    def test_view_model_instance(self):
        from bodhi.views import view_model_instance
        request = testing.DummyRequest()
        context = DBSession.query(Release).first()
        info = view_model_instance(context, request)
        self.assertEqual(type(info['context']), context.__class__)

    def test_view_model(self):
        from bodhi.resources import ReleaseResource
        from bodhi.views import view_model
        request = testing.DummyRequest()
        info = view_model(ReleaseResource, request)
        self.assertEqual(len(info['page']), 1)
        self.assertEqual(info['caption'], 'Releases')
