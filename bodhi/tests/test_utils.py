from bodhi.models import Update
from bodhi.util import get_db_from_config, get_critpath_pkgs
from bodhi.config import config


class TestUtils(object):

    def test_config(self):
        assert config.get('sqlalchemy.url'), config
        assert config['sqlalchemy.url'], config

    def test_get_db_from_config(self):
        db = get_db_from_config(dev=True)
        num = db.query(Update).count()
        assert num == 0, num

    def test_get_critpath_pkgs(self):
        """Ensure the pkgdb's critpath API works"""
        pkgs = get_critpath_pkgs()
        assert 'kernel' in pkgs, pkgs
