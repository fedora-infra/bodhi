# $Id: $

import os
import turbogears

from turbogears import testutil, database
turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

import urllib
import cherrypy
import simplejson

from sqlobject import SQLObjectNotFound
from bodhi.model import PackageUpdate, Bugzilla
from bodhi.controllers import Root
from bodhi.tools.bodhi_client import BodhiClient
from bodhi.tests.test_controllers import login, create_release

cherrypy.root = Root()


class BodhiTestClient(BodhiClient):
    """
        Overridden BodhiClient that will send requests to our test CherryPy
        root that we create in this test.  CherryPy does not listen to a socket
        in these test cases, thus we need to call the controllers directly
    """
    def __init__(self, *args, **kw):
        BodhiClient.__init__(self, *args, **kw)
        self.cookie = login()

    def login(self, *args, **kw):
        pass

    def send_request(self, method, auth=False, input=None):
        """ overload the BaseClient.send_request """
        pairs = urllib.urlencode(input)
        url = '/updates/' + method + '?%s&tg_format=json' % pairs
        testutil.createRequest(url, headers=self.cookie, method='POST')
        return simplejson.loads(cherrypy.response.body[0])

class Opts:
    """ To represent our OptionParser """
    release = 'f7'
    type = 'bugfix'
    notes = 'foo'
    bugs = '12345,6789'
    limit = 10
    delete = 'TurboGears-1.0.3.2-1.fc7'
    obsolete = 'TurboGears-1.0.3.2-1.fc7'
    comment = 'test comment'
    karma = '-1'
    request = 'stable'
    update = 'TurboGears-1.0.3.2-1.fc7'
    input_file = '.bodhi.tmp'

class TestClient(testutil.DBTest):
    """
        A test class to perform validation on the bodhi client as well as
        the JSON exposed methods.
    """
    def __get_bodhi_client(self):
        return BodhiTestClient('http://localhost:8084/updates', 'guest', None)

    def __get_opts(self):
        create_release()
        return Opts()

    def test_new_update(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)
        update = PackageUpdate.byTitle(build)
        assert update and update.title == build
        assert update.release.name == opts.release.upper()
        assert update.type == opts.type
        assert update.notes == opts.notes
        for bug in opts.bugs.split(','):
            bz = Bugzilla.byBz_id(int(bug))
            assert bz in update.bugs

    def test_list(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)
        args = { 'release' : 'f7' }
        data = bodhi.send_request('list', input=args)
        update = data['updates'][0]
        assert 'Release: Fedora 7' in update
        assert build in update
        assert 'Type: %s' % opts.type in update
        assert 'Notes: %s' % opts.notes in update

    def test_delete(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)
        assert PackageUpdate.byTitle(build)
        params = { 'update' : build }
        data = bodhi.send_request('delete', input=params, auth=True)
        try:
            PackageUpdate.byTitle(build)
            assert False, "Update not deleted properly"
        except SQLObjectNotFound:
            pass

    def test_comment(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)
        assert PackageUpdate.byTitle(build)
        bodhi.comment(opts, build)
        update = PackageUpdate.byTitle(build)
        assert len(update.comments) == 1
        assert update.comments[0].text == opts.comment
        assert update.karma == int(opts.karma)

    def test_request(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)
        assert PackageUpdate.byTitle(build)
        bodhi.request(opts, build)
        update = PackageUpdate.byTitle(build)
        assert update.request == 'stable'
        opts.request = 'testing'
        bodhi.request(opts, build)
        update = PackageUpdate.byTitle(build)
        assert update.request == 'testing'

    def test_mine(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)
        assert PackageUpdate.byTitle(build)
        data = bodhi.send_request('mine', input={}, auth=True)
        print data
        assert data['title'] == u"lmacken's updates"
        assert len(data['updates']) == 1

    def test_file_input(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()

        out = file(opts.input_file, 'w')
        out.write('type=E\nrequest=T\nbug=123,456\nbar')
        out.close()

        bodhi.parse_file(opts)
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)

        update = PackageUpdate.byTitle(build)
        assert update.type == 'enhancement'
        assert update.request == 'testing'
        assert update.notes == 'foo\r\nbar'
        for bug in (123, 456):
            bz = Bugzilla.byBz_id(bug)
            assert bz in update.bugs

        os.unlink(opts.input_file)

    def test_unpush(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        build = 'TurboGears-1.0.3.2-1.fc7'
        bodhi.new(build, opts)
        opts.request = 'unpush'
        bodhi.request(opts, build)
        update = PackageUpdate.byTitle(build)
        assert update.status == 'pending'
