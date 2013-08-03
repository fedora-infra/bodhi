from bodhi.util import load_config, get_db_from_config, get_critpath_pkgs

class TestUtils(object):

    def test_load_config(self):
        config = load_config()
        assert config.get('sqlalchemy.url'), config

    def test_get_db_from_config(self):
        from bodhi.models import Update
        db = get_db_from_config(dev=True)
        num = db.query(Update).count()
        assert num == 0, num

    def test_get_critpath_pkgs(self):
        """Ensure the pkgdb's critpath API works"""
        pkgs = get_critpath_pkgs()
        assert 'kernel' in pkgs, pkgs
