# $Id: test_controllers.py,v 1.3 2006/12/31 09:10:25 lmacken Exp $

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

import urllib
import cherrypy
import turbogears

from pprint import pprint
from turbogears import testutil, database, config

from bodhi.model import Release, PackageUpdate, User
from bodhi.controllers import Root

database.set_db_uri("sqlite:///:memory:")
cherrypy.root = Root()

turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')

class TestControllers(testutil.DBTest):

    def save_update(self, params):
        pairs = urllib.urlencode(params)
        url = '/updates/save?' + pairs
        print url
        testutil.createRequest(url)

    def login(self):
        guest = User(user_name='guest')
        guest.password = 'guest'
        print guest
        testutil.createRequest('/updates/login?tg_format=json&login=Login&forward_url=/updates/&user_name=guest&password=guest', method='POST')
        assert cherrypy.response.status == '200 OK'
        cookies = filter(lambda x: x[0] == 'Set-Cookie', cherrypy.response.header_list)
        return cookies

    def test_bad_password(self):
        x = testutil.createRequest('/updates/login?tg_format=json&login=Login&forward_url=/updates/&user_name=guest&password=foo', method='POST')
        assert "The credentials you supplied were not correct or did not grant access to this resource." in cherrypy.response.body[0]
        assert cherrypy.response.status == '403 Forbidden'

    def test_unauthenticated_update(self):
        cookies = self.login()
        print cookies
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234 5678',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params)
        assert "You must provide your credentials before accessing this resource." in cherrypy.response.body[0]
