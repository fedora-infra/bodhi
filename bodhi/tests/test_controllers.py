# $Id: test_controllers.py,v 1.3 2006/12/31 09:10:25 lmacken Exp $

"""
import cherrypy

#from turbogears import testutil
from turbogears import config, testutil, database
from bodhi.controllers import Root
from bodhi.model import Package, Arch, Release, PackageUpdate

database.set_db_uri("sqlite:///:memory:")

turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')

cherrypy.root = Root()

class TestPush(testutil.DBTest):

    def test_push():
        pkg = Package(name='foobar')
        arch = Arch(name='i386', subarches=['i686', 'athlon'])
        rel = Release(name='fc7', long_name='Fedora Core 7')
        rel.addArch(arch)
        up = PackageUpdate(nvr='mutt-1.4.2.2-4.fc7', package=pkg, release=rel,
                           submitter='lmacken@fedoraproject.org',
                           testing=True, type='security',
                           notes='Update notes and such')
        assert up.nvr == 'mutt-1.4.2.2-4.fc7'

"""

#def test_method():
#    "the index method should return a string called now"
#    import types
#    result = testutil.call(cherrypy.root.index)
#    assert type(result["now"]) == types.StringType
#
#def test_indextitle():
#    "The mainpage should have the right title"
#    testutil.createRequest("/")
#    assert "<TITLE>Welcome to TurboGears</TITLE>" in cherrypy.response.body[0]
