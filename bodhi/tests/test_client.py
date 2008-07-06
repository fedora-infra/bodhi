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

    def send_request(self, method, auth=False, req_params=None):
        """ overload the BaseClient.send_request """
        pairs = urllib.urlencode(req_params)
        url = '/updates/' + method + '?%s&tg_format=json' % pairs
        print "url =", url
        testutil.create_request(url, headers=self.cookie, method='POST')
        return simplejson.loads(cherrypy.response.body[0])

class Opts(object):
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
    build = 'TurboGears-1.0.3.2-1.fc7'

    def setUp(self):
        testutil.DBTest.setUp(self)
        turbogears.startup.startTurboGears()

    def tearDown(self):
        turbogears.startup.stopTurboGears()
        testutil.DBTest.tearDown(self)

    def __get_bodhi_client(self):
        return BodhiTestClient(base_url='http://localhost:8084/updates',
                               username='guest', password='guest')

    def __get_opts(self):
        create_release()
        return Opts()

    def test_new_update(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        testutil.capture_log(['bodhi.controllers', 'bodhi.util'])
        self.__save_update(self.build, opts, bodhi)
        testutil.print_log()
        print PackageUpdate.select().count()
        update = PackageUpdate.byTitle(self.build)
        assert update and update.title == self.build
        assert update.release.name == opts.release.upper()
        assert update.type == opts.type
        assert update.notes == opts.notes
        for bug in opts.bugs.split(','):
            bz = Bugzilla.byBz_id(int(bug))
            assert bz in update.bugs

    def __save_update(self, build, opts, bodhi):
        bodhi.save(builds=build, release=opts.release, type=opts.type,
                   bugs=opts.bugs, notes=opts.notes, request=opts.request)

    def test_list(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        self.__save_update(self.build, opts, bodhi)
        args = {'release': 'f7'}
        data = bodhi.list(**args)
        update = data['updates'][0]
        assert update['release']['long_name'] == u'Fedora 7'
        assert update['builds'][0]['nvr'] == self.build
        assert update['type'] == opts.type
        assert update['notes'] == opts.notes

    def test_delete(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        self.__save_update(self.build, opts, bodhi)
        assert PackageUpdate.byTitle(self.build)
        data = bodhi.delete(update=self.build)
        try:
            PackageUpdate.byTitle(self.build)
            assert False, "Update not deleted properly"
        except SQLObjectNotFound:
            pass

    def test_comment(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        self.__save_update(self.build, opts, bodhi)
        assert PackageUpdate.byTitle(self.build)
        testutil.capture_log(['bodhi.controllers', 'bodhi.util'])
        bodhi.comment(update=self.build, comment=opts.comment, karma=opts.karma)
        testutil.print_log()
        update = PackageUpdate.byTitle(self.build)
        assert len(update.comments) == 2, update.comments
        assert update.comments[1].text == opts.comment
        print "update.karma =", update.karma
        assert update.karma == int(opts.karma)
        bodhi.comment(update=self.build, comment=opts.comment, karma=1)
        update = PackageUpdate.byTitle(self.build)
        assert len(update.comments) == 3, update.comments
        assert update.karma == int(opts.karma) + 2

    def test_request(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        self.__save_update(self.build, opts, bodhi)
        assert PackageUpdate.byTitle(self.build)
        bodhi.request(update=self.build, request=opts.request)
        update = PackageUpdate.byTitle(self.build)
        assert update.request == 'stable'
        opts.request = 'testing'
        bodhi.request(update=self.build, request=opts.request)
        update = PackageUpdate.byTitle(self.build)
        assert update.request == 'testing'

    def test_mine(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        self.__save_update(self.build, opts, bodhi)
        assert PackageUpdate.byTitle(self.build)
        data = bodhi.list(mine=True)
        assert data['title'] == u"1 update found", repr(data)
        assert len(data['updates']) == 1

    def test_file_input(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()

        out = file(opts.input_file, 'w')
        out.write('type=E\nrequest=T\nbug=123,456\nbar')
        out.close()

        update = bodhi.parse_file(input_file=opts.input_file)
        for key, value in update.items():
            print "Overwriting %s on opts to %s" % (key, value)
            setattr(opts, key, value)
        self.__save_update(self.build, opts, bodhi)

        update = PackageUpdate.byTitle(self.build)
        assert update.type == 'enhancement'
        assert update.request == 'testing'
        assert update.notes == 'bar', repr(update.notes)
        for bug in (123, 456):
            bz = Bugzilla.byBz_id(bug)
            assert bz in update.bugs

        os.unlink(opts.input_file)

    def test_unpush(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        self.__save_update(self.build, opts, bodhi)
        opts.request = 'unpush'
        bodhi.request(update=self.build, request=opts.request)
        update = PackageUpdate.byTitle(self.build)
        assert update.status == 'pending'

    def test_update_str(self):
        bodhi = self.__get_bodhi_client()
        opts = self.__get_opts()
        self.__save_update(self.build, opts, bodhi)
        update = bodhi.list()['updates'][0]
        assert update and isinstance(update, dict)
        assert bodhi.update_str(update).startswith(u'================================================================================\n     TurboGears-1.0.3.2-1.fc7\n================================================================================\n    Release: Fedora 7\n     Status: pending\n       Type: bugfix\n      Karma: 0\n    Request: stable\n       Bugs: 12345 - None\n           : 6789 - None\n      Notes: foo\n  Submitter: guest\n')
        assert bodhi.update_str(update).endswith(u' (karma 0)\n             This update has been submitted for stable\n\n  http://localhost:8084/updates/TurboGears-1.0.3.2-1.fc7\n')
