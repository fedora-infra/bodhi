import unittest

from pyramid import testing

from bodhi.models import DBSession, Release

class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_view_model(self):
        from bodhi.views import view_model_instance
        request = testing.DummyRequest()
        context = DBSession.query(Release).first()
        info = view_model_instance(context, request)
        self.assertEqual(info['context'], {
            'candidate_tag': u'dist-f11-updates-candidate',
            'dist_tag': u'dist-f11',
            'id': 1,
            'id_prefix': u'FEDORA',
            'locked': False,
            'long_name': u'Fedora 11',
            'metrics': {'test_metric': [0, 1, 2, 3, 4]},
            'name': u'F11',
            'stable_tag': u'dist-f11-updates',
            'testing_tag': u'dist-f11-updates-testing',
            'version': 11
            })
