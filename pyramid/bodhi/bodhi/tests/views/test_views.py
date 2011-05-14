import unittest

from pyramid import testing

from bodhi.models import DBSession, Release

class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_view_model_instance(self):
        from bodhi.views import view_model_instance
        request = testing.DummyRequest()
        context = DBSession.query(Release).first()
        info = view_model_instance(context, request)
        self.assertEqual(info['context'], context.__json__())

    def test_view_model(self):
        from bodhi.resources import ReleaseResource
        from bodhi.views import view_model
        request = testing.DummyRequest()
        info = view_model(ReleaseResource, request)
        self.assertEqual(len(info['entries']), 2)
