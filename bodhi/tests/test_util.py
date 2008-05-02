from bodhi.util import Singleton

class TestUtil:

    def test_singleton(self):
        """ Make sure our Singleton class actually works """
        class A(Singleton):
            pass
        a = A()
        assert a
        b = A()
        assert b is a
