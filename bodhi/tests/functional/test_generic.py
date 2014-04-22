import bodhi.tests.functional.base


class TestGenericViews(bodhi.tests.functional.base.BaseWSGICase):

    def test_home(self):
        res = self.app.get('/', status=200)
        assert 'Logout' in res, res
