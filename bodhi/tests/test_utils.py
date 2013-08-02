from bodhi.util import load_config

class TestUtils(object):

    def test_load_config(self):
        config = load_config()
        assert config.get('sqlalchemy.url'), config
