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

    def test_release_view_json(self):
        res = app.get('/releases/F17', status=200)
        data = json.loads(res.body)
        eq_(data['context']['name'], 'F17')

    def test_invalid_release(self):
        app.get('/releases/F16', status=404)

    def test_releases_view_json(self):
        res = app.get('/releases', status=200)
        data = json.loads(res.body)
        eq_(data[u'entries'][0][u'name'], 'F15')

    def test_releases_view_invalid_bug(self):
        res = app.get('/bugs/abc', status=404)

    def test_releases_view_bug(self):
        res = app.get('/bugs/12345', status=200)
        data = json.loads(res.body)
        eq_(data[u'context'][u'bug_id'], 12345)
