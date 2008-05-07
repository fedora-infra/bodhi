# $Id: test_controllers.py,v 1.3 2006/12/31 09:10:25 lmacken Exp $

import turbogears
from turbogears import testutil, database
turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

import urllib
import cherrypy

from sqlobject import SQLObjectNotFound
from bodhi.model import Release, PackageUpdate, User, PackageBuild, Bugzilla, \
                        Group
from bodhi.controllers import Root

cherrypy.root = Root()

def create_release(num='7'):
    rel = Release(name='F'+num, long_name='Fedora '+num, id_prefix='FEDORA',
                  dist_tag='dist-fc'+num)
    assert rel
    assert rel.name == 'F'+num
    return rel

def login(username='lmacken', display_name='lmacken', group=None):
    guest = User(user_name=username, display_name=display_name)
    guest.password = 'guest'
    if group:
        group = Group(group_name=group, display_name=group)
        guest.addGroup(group)
    testutil.create_request('/updates/login?tg_format=json&login=Login&forward_url=/updates/&user_name=%s&password=guest' % username, method='POST')
    assert cherrypy.response.status == '200 OK'
    cookies = filter(lambda x: x[0] == 'Set-Cookie',
                     cherrypy.response.header_list)
    cookiehdr = cookies[0][1].strip()
    return { 'Cookie' : cookiehdr }

class TestControllers(testutil.DBTest):

    def setUp(self):
        testutil.DBTest.setUp(self)
        turbogears.startup.startTurboGears()

    def tearDown(self):
        testutil.DBTest.tearDown(self)
        turbogears.startup.stopTurboGears()

    def save_update(self, params, session={}):
        pairs = urllib.urlencode(params)
        url = '/updates/save?' + pairs
        print url
        testutil.create_request(url, headers=session, method='POST')

    def test_bad_password(self):
        x = testutil.create_request('/updates/login?tg_format=json&login=Login&user_name=lmacken&password=foo', method='POST')
        assert "The credentials you supplied were not correct or did not grant access to this resource." in cherrypy.response.body[0]
        print cherrypy.response.status

        # We commented out the cherrypy.response.status = '403' in 
        # our login controller to get the cli tool working.  This may be a
        # good/bad thing?
        #assert cherrypy.response.status == '403 Forbidden'

    def test_good_password(self):
        guest = User(user_name='lmacken')
        guest.password = 'guest'
        x = testutil.create_request('/updates/login?tg_format=json&login=Login&user_name=lmacken&password=guest', method='POST')
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
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)
        assert "This resource resides temporarily at <a href='http://localhost/updates/F7/pending/TurboGears-1.0.2.2-2.fc7'>http://localhost/updates/F7/pending/TurboGears-1.0.2.2-2.fc7</a>" in cherrypy.response.body[0], cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        assert update.bugs[0].bz_id == int(params['bugs'])
        assert update.notes == params['notes']

    def test_multibuild_update(self):
        session = login()
        create_release()
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
        session = login()
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

    def test_bad_type(self):
        session = login()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'REGRESSION!',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        print cherrypy.response.body[0]
        assert "Value must be one of: bugfix; enhancement; security (not u'REGRESSION!')" in cherrypy.response.body[0]

    def test_user_notes_encoding(self):
        session = login(username='lmacken', display_name='foo\xc3\xa9bar')
        create_release()
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
        session = login()
        create_release()
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
        session = login()
        create_release()
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
        x = testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' % 
                                   params['builds'], method='POST',
                                   headers=session)
        assert len(update.comments) == 1
        assert update.karma == 1
        assert update.comments[0].author == 'lmacken'
        assert update.comments[0].text == 'foobar'

        # Allow users to negate their original comment
        x = testutil.create_request('/updates/comment?text=bizbaz&title=%s&karma=-1' %
                                   params['builds'], method='POST',
                                   headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 0

        # but don't let them do it again
        x = testutil.create_request('/updates/comment?text=bizbaz&title=%s&karma=-1' %
                                   params['builds'], method='POST',
                                   headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 0

        # Add a new comment, and make sure we can access the comments in the proper order
        x = testutil.create_request('/updates/comment?text=woopdywoop&title=%s' %
                                   params['builds'], method='POST',
                                   headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert len(update.get_comments()) == 4
        assert update.get_comments()[-1].text == 'woopdywoop', update.get_comments()

    # TODO:
    # - duplicate titles with updates

    def test_multi_release(self):
        session = login()
        f7 = create_release()
        f8 = create_release('8')
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 TurboGears-1.0.4.4-1.fc8',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        f7build, f8build = params['builds'].split()
        f8up = PackageUpdate.byTitle(f8build)
        assert f8up

    def test_edit(self):
        session = login()
        create_release()
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

        # Make sure there are no stray builds
        for update in PackageUpdate.select():
            assert len(update.builds), "%s with no builds!" % update.title

        for build in PackageBuild.select():
            assert len(build.updates), "%s has no updates!" % build.nvr

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

        # Try editing this update, with some parameters that will fail
        params = {
            'builds'  : 'python-sqlobject-0.8.2-1.fc7 kernel-2.6.20-1',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foobar',
            'edited'  : 'python-sqlobject-0.8.2-1.fc7'
        }
        self.save_update(params, session)
        try:
            update = PackageUpdate.byTitle(','.join(params['builds'].split()))
            assert False
        except SQLObjectNotFound:
            pass

        # Make sure there are no stray builds
        for update in PackageUpdate.select():
            assert len(update.builds), "%s with no builds!" % update.title

        # Make sure the update is still in tact
        update = PackageUpdate.byTitle('python-sqlobject-0.8.2-1.fc7')
        assert len(update.builds) == 1

    def test_delete(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7,python-sqlobject-1.6.3-13.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : ''
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Try unauthenticated first
        x = testutil.create_request('/updates/delete?update=%s' % 
                                   params['builds'], method='POST')
        update = PackageUpdate.byTitle(params['builds'])
        assert update

        # Now try again with our authenticated session cookie
        x = testutil.create_request('/updates/delete?update=%s' % 
                                   params['builds'], method='POST',
                                   headers=session)
        try:
            update = PackageUpdate.byTitle(params['builds'])
            print update
            assert False, "Update never deleted!"
        except SQLObjectNotFound:
            pass

        for build in params['builds'].split(','):
            try:
                build = PackageBuild.byNvr(build)
                print build
                assert False, "Build never deleted!"
            except SQLObjectNotFound:
                pass

    def test_requests(self):
        session = login()
        create_release()
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
        assert update.request == 'testing'

        testutil.create_request('/updates/request/testing/%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        testutil.create_request('/updates/request/unpush/%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'
        assert update.pushed == False
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable'

    def test_unauthorized_request(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : '',
            'request' : 'testing',
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        update.submitter = 'bobvila'
        testutil.create_request('/updates/request?action=stable&update=%s' %
                                params['builds'])
        assert "You must provide your credentials before accessing this resource." in cherrypy.response.body[0]

    def test_invalid_request(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : '',
            'request' : 'foobar!',
        }
        self.save_update(params, session)
        assert "Value must be one of: Testing; Stable; None; testing; stable; none (not u'foobar!')" in cherrypy.response.body[0]

    def test_cve_bugs(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : 'CVE-2007-5201',
                'cves'    : '',
                'notes'   : ''
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.bugs[0].bz_id == 293081
        # disabled for now, since we want to try and avoid as much bugzilla
        # contact during our test cases as possible :)
        #assert update.bugs[0].title == "CVE-2007-5201 Duplicity discloses password in FTP backend"

    def test_not_owner(self):
        session = login(username='guest')
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '',
                'cves'    : '',
                'notes'   : ''
        }
        self.save_update(params, session)
        assert "This resource resides temporarily" in cherrypy.response.body[0], cherrypy.response.body[0]

    def test_obsoleting(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar',
                'request' : None
        }
        self.save_update(params, session)
        assert "This resource resides temporarily at <a href='http://localhost/updates/F7/pending/TurboGears-1.0.2.2-2.fc7'>http://localhost/updates/F7/pending/TurboGears-1.0.2.2-2.fc7</a>" in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'

        # Throw a newer build in, which should obsolete the previous
        newparams = {
                'builds'  : 'TurboGears-1.0.2.2-3.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '4321',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(newparams, session)
        print cherrypy.response.body[0]
        newupdate = PackageUpdate.byTitle(newparams['builds'])
        assert newupdate.status == 'pending'
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'obsolete'

        # The newer build should also inherit the obsolete updates bugs
        bugz = [bug.bz_id for bug in newupdate.bugs]
        assert 1234 in bugz and 4321 in bugz

    def test_obsoleting_request(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)
        assert "This resource resides temporarily at <a href='http://localhost/updates/F7/pending/TurboGears-1.0.2.2-2.fc7'>http://localhost/updates/F7/pending/TurboGears-1.0.2.2-2.fc7</a>" in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'
        assert update.request == 'testing'

        # Throw a newer build in, which should *NOT* obsolete the previous,
        # since it has an active request
        newparams = {
                'builds'  : 'TurboGears-1.0.2.2-3.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '4321',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(newparams, session)
        newupdate = PackageUpdate.byTitle(newparams['builds'])
        assert newupdate.status == 'pending'
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'

    def test_list(self):
        """
        This unittest verifies various aspects of the generic list controller
        that bodhi provides.  This method is utilized by both the web interface
        and the command-line client.
        """
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : '',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)

        url = '/updates/list?' + urllib.urlencode({ 'release' : 'F7' })
        testutil.create_request(url, method='GET')
        assert "1 updates found" in cherrypy.response.body[0], cherrypy.response.body[0]

        url = '/updates/list?' + urllib.urlencode({
                'release' : 'F7',
                'bugs'    : '1234'
        })
        testutil.create_request(url, method='GET')
        assert "1 updates found" in cherrypy.response.body[0]

        url = '/updates/list?' + urllib.urlencode({
                'release' : 'F7',
                'bugs'    : '1234',
                'type'    : 'enhancement'
        })
        testutil.create_request(url, method='GET')
        assert "1 updates found" in cherrypy.response.body[0]

        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type'    : 'security',
                'bugs'    : '321',
                'cves'    : '',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)

    def test_default_request(self):
        """
        Verify that updates are automatically submitted to testing, and that
        this actually happens
        """
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '321',
                'cves'    : '',
                'notes'   : 'foobar',
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        params = {
                'builds'  : 'python-sqlobject-1.6.3-13.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '321',
                'cves'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable'
        params = {
                'builds'  : 'nethack-2.10-3.20070831cvs.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '321',
                'cves'    : '',
                'notes'   : 'foobar',
                'request' : 'None'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == None
        params = {
                'builds'  : 'xprobe2-1.4.6-1.fc7',
                'release' : 'Fedora 7',
                'type'    : 'enhancement',
                'bugs'    : '321',
                'cves'    : '',
                'notes'   : 'foobar',
                'request' : 'Testing'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'

    def test_security_approval(self):
        """
        Make sure that security updates require approval from the security
        response team before being pushed to stable
        """
        session = login(group='security_respons')
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        assert not update.approved

        url = '/updates/approve?update=' + params['builds']
        testutil.create_request(url, headers=session, method='POST')
        update = PackageUpdate.byTitle(params['builds'])
        assert update.approved
        assert update.request == 'stable'

    def test_cached_acls(self):
        """
        Make sure that the list of committers for this package is getting
        updated in our db for each submission.
        """
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert 'lmacken' in update.builds[0].package.committers

    def test_bug_aliases(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type'    : 'security',
                'bugs'    : 'CVE-2007-2435',
                'notes'   : 'foobar',
                'request' : 'Stable'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.bugs[0].bz_id == 239660
