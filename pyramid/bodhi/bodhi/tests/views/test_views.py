import unittest

from pyramid import testing

class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_my_view(self):
        from bodhi.views import view_root
        request = testing.DummyRequest()
        context = []
        info = view_root(context, request)
        self.assertEqual(info['project'], 'bodhi')
