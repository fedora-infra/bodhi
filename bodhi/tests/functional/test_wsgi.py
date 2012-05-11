import unittest
import json
import tw2.core as twc

from nose.tools import eq_
from bodhi.models import DBSession

app = None


def setup():
    from bodhi import main
    from webtest import TestApp
    global app
    app = main({}, **{'sqlalchemy.url': 'sqlite://',
                      'mako.directories': 'bodhi:templates'})
    app = TestApp(twc.make_middleware(app))


class FunctionalTests(unittest.TestCase):

    def get_update(self, builds=None):
        if not builds:
            builds = ['bodhi-2.0-1']
        return {
            'newupdateform:packages:0:package': builds,
            'newupdateform:bugs:bugs': u'',
            'newupdateform:notes': u'this is a test update',
            'newupdateform:type_': u'bugfix',
            'newupdateform:karma:stablekarma': u'3',
            'newupdateform:karma:unstablekarma': u'-3',
            'newupdateform:id': u'',
            }

    def test_release_view_json(self):
        res = app.get('/releases/F17', status=200)
        data = json.loads(res.body)
        eq_(data['context']['name'], 'F17')

    def test_invalid_release(self):
        app.get('/releases/F16', status=404)

    def test_releases_view_json(self):
        res = app.get('/releases', status=200)
        data = json.loads(res.body)
        eq_(data[u'entries'][0][u'name'], 'F17')

    def test_releases_view_invalid_bug(self):
        app.get('/bugs/abc', status=404)

    def test_releases_view_bug(self):
        res = app.get('/bugs/12345', status=200)
        data = json.loads(res.body)
        eq_(data[u'context'][u'bug_id'], 12345)

    def test_invalid_build_name(self):
        res = app.post('/save', self.get_update('invalidbuild-1.0'))
        assert 'Invalid build' in res, res

    def test_valid_tag(self):
        res = app.post('/save', self.get_update())
        assert 'Invalid tag' not in res, res

    def test_invalid_tag(self):
        res = app.post('/save', self.get_update('bodhi-1.0-1'))
        assert 'Invalid tag' in res, res
