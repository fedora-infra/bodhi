import bodhi.tests.functional.base


class TestGenericViews(bodhi.tests.functional.base.BaseWSGICase):

    def test_home(self):
        res = self.app.get('/', status=200)
        self.assertIn('Logout', res)
        self.assertIn('Help test Fedora', res)

    def test_markdown(self):
        res = self.app.get('/markdown', {'text': 'wat'}, status=200)
        self.assertEquals(res.json_body['html'], '<p>wat</p>')
