import unittest
import json

from nose.tools import eq_

app = None

def setup():
    from bodhi import main
    from webtest import TestApp
    global app
    app = main({}, **{'sqlalchemy.url': 'sqlite://'})
    app = TestApp(app)

class FunctionalTests(unittest.TestCase):

    def test_release_view_json(self):
        res = app.get('/releases/F15', status=200)
        data = json.loads(res.body)
        eq_(data['context']['name'], 'F15')

    def test_invalid_release(self):
        app.get('/releases/F16', status=404)

    def test_releases_view_json(self):
        res = app.get('/releases', status=200)
        data = json.loads(res.body)
        eq_(data[u'entries'][0][u'name'], 'F15')

