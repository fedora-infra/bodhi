# $Id: test_controllers.py,v 1.3 2006/12/31 09:10:25 lmacken Exp $

import turbogears
from turbogears import testutil, database, config
turbogears.update_config(configfile='dev.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

import urllib
import cherrypy

from sqlobject import SQLObjectNotFound
from bodhi.model import Release, PackageUpdate, User, PackageBuild, Bugzilla
from bodhi.controllers import Root

cherrypy.root = Root()

class TestControllers(testutil.DBTest):

    def save_update(self, params, session={}):
        pairs = urllib.urlencode(params)
        url = '/updates/save?' + pairs
        print url
        testutil.createRequest(url, headers=session, method='POST')

    def create_release(self):
        rel = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                      dist_tag='dist-fc7')
        assert rel

    def login(self, username='guest', display_name='guest'):
        guest = User(user_name=username, display_name=display_name)
        guest.password = 'guest'
        testutil.createRequest('/updates/login?tg_format=json&login=Login&forward_url=/updates/&user_name=guest&password=guest', method='POST')
        assert cherrypy.response.status == '200 OK'
        cookies = filter(lambda x: x[0] == 'Set-Cookie',
                         cherrypy.response.header_list)
        cookiehdr = ""
        for cookie in zip(cookies[0], cookies[1])[1]:
            cookiehdr += cookie.split(';')[0] + '\r\n '
        cookiehdr = cookiehdr.strip()
        return { 'Cookie' : cookiehdr }

    def test_bad_password(self):
        x = testutil.createRequest('/updates/login?tg_format=json&login=Login&&user_name=guest&password=foo', method='POST')
        assert "The credentials you supplied were not correct or did not grant access to this resource." in cherrypy.response.body[0]
        print cherrypy.response.status

        # We commented out the cherrypy.response.status = '403' in 
        # our login controller to get the cli tool working.  This may be a
        # good/bad thing?
        #assert cherrypy.response.status == '403 Forbidden'

    def test_good_password(self):
        guest = User(user_name='guest')
        guest.password = 'guest'
        x = testutil.createRequest('/updates/login?tg_format=json&login=Login&user_name=guest&password=guest', method='POST')
        assert cherrypy.response.status == '200 OK'

    def test_unauthenticated_update(self):
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

    def test_new_update(self):
        session = self.login()
        self.create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        assert update.bugs[0].bz_id == int(params['bugs'])
        assert update.cves[0].cve_id == params['cves']
        assert update.notes == params['notes']
        # we specified a CVE, so bodhi will automatically change the type
        assert update.type == 'security'

    def test_multibuild_update(self):
        session = self.login()
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type'    : 'enhancement',
            'bugs'    : '1234 5678',
            'cves'    : '',
            'notes'   : 'foobar'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))
        assert update
        builds = map(lambda x: x.nvr, update.builds)
        for build in params['builds'].split():
            assert build in builds
        assert update.release.long_name == params['release']
        assert update.type == params['type']
        assert update.notes == params['notes']
        for bug in params['bugs'].split():
            assert int(bug) in map(lambda x: x.bz_id, update.bugs)

    def test_bad_build(self):
        session = self.login()
        params = {
            'builds'  : 'foobar',
            'release' : 'Fedora 7',
            'type'    : 'enhancement',
            'bugs'    : '1234 5678',
            'cves'    : '',
            'notes'   : 'foobar'
        }
        self.save_update(params, session)
        assert "Invalid package name; must be in package-version-release format" in cherrypy.response.body[0]

    def test_bad_release(self):
        session = self.login()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Ubuntu Bitchy Beaver',
            'type'    : 'enhancement',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        assert "Value must be one of: F7; Fedora 7 (not \'Ubuntu Bitchy Beaver\')" in cherrypy.response.body[0]

    def test_bad_type(self):
        session = self.login()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'REGRESSION!',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        assert "Value must be one of: bugfix; enhancement; security (not \'REGRESSION!\')" in cherrypy.response.body[0]

    def test_user_notes_encoding(self):
        session = self.login(username='guest', display_name='foo\xc3\xa9bar')
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'Foo\u2019bar'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        assert update.notes == params['notes']

    def test_bugs_update(self):
        session = self.login()
        self.create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '#1234, #567 89',
                'cves'    : '',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        for bug in params['bugs'].replace('#', '').replace(',', ' ').split():
            assert int(bug) in map(lambda x: x.bz_id, update.bugs)
        assert len(update.cves) == 0
        assert update.notes == params['notes']
        assert update.type == params['type']

    def test_comment(self):
        session = self.login()
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        x = testutil.createRequest('/updates/comment?text=foobar&title=%s&karma=1' % 
                                   params['builds'], method='POST',
                                   headers=session)
        assert len(update.comments) == 1
        assert update.karma == 1
        assert update.comments[0].author == 'guest'
        assert update.comments[0].text == 'foobar'

        # Allow users to negate their original comment
        x = testutil.createRequest('/updates/comment?text=bizbaz&title=%s&karma=-1' %
                                   params['builds'], method='POST',
                                   headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 0

        # but don't let them do it again
        x = testutil.createRequest('/updates/comment?text=bizbaz&title=%s&karma=-1' %
                                   params['builds'], method='POST',
                                   headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 0

    def test_edit(self):
        session = self.login()
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Add another build, and a bug
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : '',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))
        assert len(update.builds) == 2
        builds = map(lambda x: x.nvr, update.builds)
        for build in params['builds'].split():
            assert build in builds
            x = PackageBuild.byNvr(build)
            assert x.updates[0] == update
        assert len(update.bugs) == 1
        assert update.bugs[0].bz_id == int(params['bugs'])
        bug = Bugzilla.byBz_id(int(params['bugs']))

        # Remove a build and bug
        params = {
            'builds'  : 'python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foobar',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7,python-sqlobject-0.8.2-1.fc7'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))
        assert len(update.builds) == 1
        build = PackageBuild.byNvr(params['builds'])
        assert build.updates[0] == update
        assert update.notes == params['notes']
        assert len(update.bugs) == 0
        try:
            bug = Bugzilla.byBz_id(1)
            assert False, "Bug #1 never got destroyed after edit"
        except SQLObjectNotFound:
            pass

    def test_delete(self):
        session = self.login()
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Try unauthenticated first
        x = testutil.createRequest('/updates/delete?update=%s' % 
                                   params['builds'], method='POST')
        update = PackageUpdate.byTitle(params['builds'])
        assert update

        # Now try again with our authenticated session cookie
        x = testutil.createRequest('/updates/delete?update=%s' % 
                                   params['builds'], method='POST',
                                   headers=session)
        try:
            update = PackageUpdate.byTitle(params['builds'])
            print update
            assert False, "Update never deleted!"
        except SQLObjectNotFound:
            pass

    def test_requests(self):
        session = self.login()
        self.create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'
        assert update.request == None

        testutil.createRequest('/updates/push?nvr=%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        print "update.request =", update.request
        assert update.request == 'testing'
        testutil.createRequest('/updates/unpush?nvr=%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'unpush'
        testutil.createRequest('/updates/move?nvr=%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable', update.request

    def test_bad_bugs(self):
        session = self.login()
        self.create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : 'foobar',
                'cves'    : '',
                'notes'   : ''
        }
        self.save_update(params, session)
        assert "Invalid bug(s)." in cherrypy.response.body[0]

    def test_bad_cves(self):
        session = self.login()
        self.create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '',
                'cves'    : 'FOO',
                'notes'   : ''
        }
        self.save_update(params, session)
        assert "Invalid CVE(s)." in cherrypy.response.body[0]
