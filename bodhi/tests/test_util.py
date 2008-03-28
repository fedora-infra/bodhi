from bodhi.util import Singleton

class TestUtil:

    def test_singleton(self):
        """ Make sure our Singleton metaclass actually works """
        class A(object): __metaclass__ = Singleton
        a = A()
        assert a
        b = A()
        assert b is a
