from turbogears import config, update_config
from bodhi.util import Singleton

update_config(configfile='bodhi.cfg', modulename='bodhi.config')

class TestUtil:

    def test_singleton(self):
        """ Make sure our Singleton class actually works """
        class A(Singleton):
            pass
        a = A()
        assert a
        b = A()
        assert b is a

    def test_acls(self):
        acl = config.get('acl_system')
        assert acl in ('dummy', 'pkgdb'), "Unknown acl system: %s" % acl
