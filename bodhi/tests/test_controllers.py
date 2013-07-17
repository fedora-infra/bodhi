# $Id: test_controllers.py,v 1.3 2006/12/31 09:10:25 lmacken Exp $
# -*- coding: utf-8 -*-

import os
import urllib
import simplejson
import turbogears
import cPickle as pickle

from urllib import urlencode
from datetime import datetime, timedelta
from sqlobject import SQLObjectNotFound
from turbogears import testutil, database, config
turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

from bodhi.model import Release, PackageUpdate, User, PackageBuild, Bugzilla, \
                        Group
from bodhi.controllers import Root
from bodhi.exceptions import DuplicateEntryError
from bodhi.jobs import refresh_metrics
from bodhi.util import sort_updates, get_nvr

import cherrypy
cherrypy.root = Root()

def create_release(num='7', dist='dist-fc', **kw):
    rel = Release(name='F'+num, long_name='Fedora '+num, id_prefix='FEDORA',
                  dist_tag=dist+num, **kw)
    assert rel
    assert Release.byName('F'+num)
    return rel

def login(username='guest', display_name='guest', group=None):
    try:
        guest = User(user_name=username, display_name=display_name,
                     password='guest')
    except DuplicateEntryError:
        guest = User.by_user_name(username)
    if group:
        try:
            group = Group(group_name=group, display_name=group)
        except DuplicateEntryError:
            group = Group.by_group_name(group)
        guest.addGroup(group)
    testutil.create_request('/updates/login?tg_format=json&login=Login&forward_url=/updates/&user_name=%s&password=guest' % username, method='POST')
    assert cherrypy.response.status == '200 OK', cherrypy.response.body[0]
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

    def save_update(self, params, session=None):
        if not session: session = {}
        pairs = urllib.urlencode(params)
        url = '/updates/save?' + pairs
        print url
        testutil.create_request(url, headers=session, method='POST')

    def test_bad_password(self):
        x = testutil.create_request('/updates/login?tg_format=json&login=Login&user_name=guest&password=foooo', method='POST')
        assert "The credentials you supplied were not correct or did not grant access to this resource." in cherrypy.response.body[0]
        print cherrypy.response.status

        # We commented out the cherrypy.response.status = '403' in
        # our login controller to get the cli tool working.  This may be a
        # good/bad thing?
        #assert cherrypy.response.status == '403 Forbidden'

    def test_good_password(self):
        guest = User(user_name='guest', password='guest')
        guest.password = 'guest'
        x = testutil.create_request('/updates/login?tg_format=json&login=Login&user_name=guest&password=guest', method='POST')
        assert cherrypy.response.status == '200 OK'

    def test_unauthenticated_update(self):
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '1234 5678',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params)
        assert "You must provide your credentials before accessing this resource." in cherrypy.response.body[0], cherrypy.response.body

    def test_new_update(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar',
                'autokarma' : True
        }
        self.save_update(params, session)
        assert "This resource resides temporarily at <a href='http://localhost/updates/TurboGears-1.0.2.2-2.fc7'>http://localhost/updates/TurboGears-1.0.2.2-2.fc7</a>" in cherrypy.response.body[0], cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        assert update.bugs[0].bz_id == int(params['bugs'])
        assert update.notes == params['notes']
        assert update.stable_karma == 3
        assert update.unstable_karma == -3

    def test_multibuild_update(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'enhancement',
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
        assert update.type == params['type_']
        assert update.notes == params['notes']
        for bug in params['bugs'].split():
            assert int(bug) in map(lambda x: x.bz_id, update.bugs)

    def test_bad_build(self):
        session = login()
        params = {
            'builds'  : 'foobar',
            'release' : 'Fedora 7',
            'type_'    : 'enhancement',
            'bugs'    : '1234 5678',
            'cves'    : '',
            'notes'   : 'foobar'
        }
        self.save_update(params, session)
        assert "Invalid package name; must be in package-version-release format" in cherrypy.response.body[0]

    def test_bad_type(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'   : 'REGRESSION!',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        cherrypy.config.update({'build_dir': '/tmp'})
        self.save_update(params, session)
        assert "Value must be one of: bugfix; enhancement; security; newpackage (not u'REGRESSION!')" in cherrypy.response.body[0]

    def test_user_notes_encoding(self):
        session = login(username='guest', display_name='foo\xc3\xa9bar')
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : u'Foo\u2019bar'.encode('utf-8')
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.title == params['builds']
        assert update.builds[0].nvr == params['builds']
        assert update.release.long_name == params['release']
        assert update.notes == unicode(params['notes'], 'utf8')

    def test_bugs_update(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
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
        assert update.type == params['type_']

    def test_comment(self):
        session = login()
        other_session = login('otherguy', 'otherguy')
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        x = testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                   params['builds'], method='POST',
                                   headers=session)
        assert len(update.comments) == 2, cherrypy.response.body[0]
        assert update.karma == 0  # Submitters cannot alter karma
        assert update.comments[1].author == 'guest'
        assert update.comments[1].text == 'foobar'

        x = testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                   params['builds'], method='POST',
                                   headers=other_session)
        assert len(update.comments) == 3, cherrypy.response.body[0]
        assert update.karma == 1
        assert update.comments[2].author == 'otherguy'
        assert update.comments[2].text == 'foobar'

        # Allow users to negate their original comment
        x = testutil.create_request('/updates/comment?text=bizbaz&title=%s&karma=-1' %
                                   params['builds'], method='POST',
                                   headers=other_session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == -1

        # but don't let them do it again
        x = testutil.create_request('/updates/comment?text=bizbaz&title=%s&karma=-1' %
                                   params['builds'], method='POST',
                                   headers=other_session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == -1

        # let them change their -1 to a +1
        x = testutil.create_request('/updates/comment?text=bizbaz&title=%s&karma=1' %
                                   params['builds'], method='POST',
                                   headers=other_session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 1, update.karma

        # Add a new comment, and make sure we can access the comments in the
        # proper order
        x = testutil.create_request('/updates/comment?text=woopdywoop&title=%s' %
                                   params['builds'], method='POST',
                                   headers=other_session)
        update = PackageUpdate.byTitle(params['builds'])
        assert len(update.get_comments()) == 7
        assert update.get_comments()[-1].text == 'woopdywoop', update.get_comments()
        assert update.get_comments()[1].text == 'foobar'

    def test_duplicate_titles(self):
        session = login()
        f8 = create_release('8', dist='dist-f')
        params = {
            'builds'  : 'TurboGears-1.0.4.4-1.fc8',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        testutil.capture_log("bodhi.util")
        self.save_update(params, session)
        f8up = PackageUpdate.byTitle(params['builds'])
        assert f8up.title == params['builds']
        self.save_update(params, session)
        log = testutil.get_log()
        assert '<a href="/updates/TurboGears-1.0.4.4-1.fc8">TurboGears-1.0.4.4-1.fc8</a> update already exists!' in log

    def test_duplicate_multibuild_same_release(self):
        session = login()
        f7 = create_release('7')
        params = {
            'builds'  : 'TurboGears-1.0.4.4-1.fc7 nethack-3.4.3-17.fc7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        testutil.capture_log("bodhi.util")
        self.save_update(params, session)
        params['builds'] = params['builds'].replace(' ', ',')
        up = PackageUpdate.byTitle(params['builds'])
        assert up.title == params['builds']

        # Remove one of the builds and then try again
        params['builds'] = params['builds'].split(',')[0]
        self.save_update(params, session)
        log = testutil.get_log()
        assert '<a href="/updates/TurboGears-1.0.4.4-1.fc7">TurboGears-1.0.4.4-1.fc7</a> update already exists!' in log

    def test_duplicate_multibuild_different_release(self):
        session = login()
        f7 = create_release('7')
        f8 = create_release('8', dist='dist-f')
        params = {
            'builds'  : 'TurboGears-1.0.4.4-1.fc7 nethack-3.4.3-17.fc8',
            'type_'    : 'bugfix',
            'bugs'    : '', 'cves'    : '', 'notes'   : 'foo'
        }
        self.save_update(params, session)
        params['builds'] = params['builds'].replace(' ', ',')

        # Make sure they were not created as a single update
        try:
            up = PackageUpdate.byTitle(params['builds'])
            assert False, "Multi-release update created as single PackageUpdate?"
        except SQLObjectNotFound:
            pass

        # Try again
        testutil.capture_log("bodhi.util")
        self.save_update(params, session)
        log = testutil.get_log()
        assert '<a href="/updates/TurboGears-1.0.4.4-1.fc7">TurboGears-1.0.4.4-1.fc7</a> update already exists!' in log

        # Remove one of the builds and then try again
        params['builds'] = params['builds'].split(',')[0]
        testutil.capture_log("bodhi.util")
        self.save_update(params, session)
        log = testutil.get_log()
        assert '<a href="/updates/TurboGears-1.0.4.4-1.fc7">TurboGears-1.0.4.4-1.fc7</a> update already exists!' in log

    def test_multi_release(self):
        session = login()
        f7 = create_release()
        f8 = create_release('8', dist='dist-f')
        print f8
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 TurboGears-1.0.4.4-1.fc8',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)
        f7build, f8build = params['builds'].split()

        f8up = PackageUpdate.byTitle(f8build)
        assert f8up
        assert f8up.title == f8build
        assert f8up.type == 'bugfix'
        assert len(f8up.builds) == 1
        assert f8up.builds[0].nvr == f8build
        assert f8up.builds[0].package.name == 'TurboGears'

        f7up = PackageUpdate.byTitle(f7build)
        assert f7up
        assert f7up.title == f7build
        assert f7up.type == 'bugfix'
        assert len(f7up.builds) == 1
        assert f7up.builds[0].nvr == f7build
        assert f7up.builds[0].package.name == 'TurboGears'

    def test_add_older_build_to_update(self):
        """ Try adding a newer build an update (#385) """
        session = login()
        f7 = create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'type_'   : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)

        # Add another build, for a different release
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7 TurboGears-1.0.2.2-1.fc7',
            'release' : 'Fedora 7',
            'type_'   : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7,python-sqlobject-0.8.2-1.fc7',
        }

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()
        up = PackageUpdate.select()[0]
        assert len(up.builds) == 2, up.builds
        assert up.title == params['edited']
        assert u'Unable to save update with conflicting builds of the same package: TurboGears-1.0.2.2-2.fc7 and TurboGears-1.0.2.2-1.fc7. Please remove one and try again.' in logs

    def test_add_newer_build_to_update(self):
        """ Try adding a newer build an update (#385) """
        session = login()
        f7 = create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'type_'   : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)

        # Add another build, for a different release
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7 TurboGears-1.0.2.2-3.fc7',
            'release' : 'Fedora 7',
            'type_'   : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7,python-sqlobject-0.8.2-1.fc7',
        }

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()
        up = PackageUpdate.select()[0]
        assert len(up.builds) == 2, up.builds
        assert up.title == params['edited']
        assert u'Unable to save update with conflicting builds of the same package: TurboGears-1.0.2.2-2.fc7 and TurboGears-1.0.2.2-3.fc7. Please remove one and try again.' in logs

    def test_add_different_release_to_update(self):
        """
        Try adding a build for a different release to an update (#251)
        """
        session = login()
        f7 = create_release()
        f8 = create_release('8', dist='dist-f')
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'type_'   : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)

        # Add another build, for a different release
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc8',
            'release' : 'Fedora 7',
            'type_'   : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7'
        }

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()
        assert 'Cannot add a F8 build to a F7 update. Please create a new update for python-sqlobject-0.8.2-1.fc8' in logs, logs
        up = PackageUpdate.byTitle(params['edited'])
        assert len(up.builds) == 1
        try:
            PackageBuild.byNvr('python-sqlobject-0.8.2-1.fc8')
            assert False, "Bad update created"
        except SQLObjectNotFound:
            pass

    def test_remove_build_and_add_different_release_to_update(self):
        """
        Try removing a build and adding a build for a different release to an
        update (#251)
        """
        session = login()
        f7 = create_release()
        f8 = create_release('8', dist='dist-f')
        orig_params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'type_'   : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(orig_params, session)
        up = PackageUpdate.byTitle(orig_params['builds'])
        assert len(up.builds) == 1

        # Add another build, for a different release
        params = {
            'builds'  : 'python-sqlobject-0.8.2-1.fc8',
            'release' : 'Fedora 7',
            'type_'   : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7'
        }

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()
        assert u"Unable to edit update" in '\n'.join(logs), logs

        # Try again without a request..
        new_build = 'python-sqlalchemy-1.0.2.2-2.fc7'
        orig_params['builds'] = new_build
        orig_params['request'] = None
        self.save_update(orig_params, session)
        assert PackageUpdate.byTitle(new_build)

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        params['edited'] = new_build
        self.save_update(params, session)
        logs = testutil.get_log()
        assert 'Cannot add a F8 build to a F7 update.' in '\n'.join(logs), logs

        up = PackageUpdate.byTitle('TurboGears-1.0.2.2-2.fc7')
        assert len(up.builds) == 1, up.builds
        b = PackageBuild.byNvr('TurboGears-1.0.2.2-2.fc7')
        assert len(b.updates) == 1
        b = PackageBuild.byNvr('python-sqlalchemy-1.0.2.2-2.fc7')
        assert len(b.updates) == 1
        assert len(b.updates[0].builds) == 1

    def test_edit(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Add another build, and a bug
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo',
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

        assert update.comments[-1].text == u'guest has edited this update. New build(s): python-sqlobject-0.8.2-1.fc7. '

        # Remove a build and bug
        params = {
            'builds'  : 'python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
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
            'type_'    : 'bugfix',
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

    def test_edit_notes(self):
        """
        Make sure we can edit the notes without having the update go back to pending
        """
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Pretend it's pushed to testing
        update.status = 'testing'
        update.request = None

        # Add another build, and a bug
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        assert update.status == 'testing'
        assert update.request == None


    def test_edit_builds(self):
        """ Make sure we can edit builds in an update """
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Pretend it's pushed to testing
        update.status = 'testing'
        update.request = None

        # Add another build, and a bug
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.1-1.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))

        assert update.status == 'pending'
        assert update.request == 'testing'

    def test_delete(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7,python-sqlobject-1.6.3-13.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
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
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)
        print cherrypy.response.body[0]
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
        assert update.request == 'testing'

    def test_unauthorized_request(self):
        session = login()
        create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'release' : 'Fedora 7',
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo',
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
            'type_'    : 'bugfix',
            'bugs'    : '',
            'cves'    : '',
            'notes'   : 'foo',
            'request' : 'foobar!',
        }
        self.save_update(params, session)
        assert "Value must be one of: Testing; Stable; None; None; testing; stable; none (not u'foobar!')" in cherrypy.response.body[0], cherrypy.response.body[0]

    #def test_broken_update_path_on_submission(self):
    #    """ Make sure we are unable to break upgrade paths upon submission """
    #    from bodhi.buildsys import get_session
    #    koji = get_session()
    #    session = login()
    #    create_release()
    #    params = {
    #        'builds'  : 'TurboGears-1.0.2.2-2.fc7',
    #        'release' : 'Fedora 7',
    #        'type_'    : 'bugfix',
    #        'bugs'    : '',
    #        'cves'    : '',
    #        'notes'   : 'foo'
    #    }

    #    # Monkey-patch our DevBuildsys
    #    from bodhi.buildsys import DevBuildsys
    #    oldGetBuild = DevBuildsys.getBuild
    #    DevBuildsys.getBuild = lambda *x, **y: {
    #            'epoch': None, 'name': 'TurboGears',
    #            'nvr': 'TurboGears-1.0.2.2-2.fc7',
    #            'release': '2.fc7',
    #            'tag_name': 'dist-fc7-updates-testing',
    #            'version': '1.0.2.2'
    #            }

    #    # Make a newer build already exist
    #    oldListTagged = DevBuildsys.listTagged
    #    DevBuildsys.listTagged = lambda *x, **y: [
    #            {'epoch': None, 'name': 'TurboGears',
    #             'nvr': 'TurboGears-1.0.2.3-2.fc7', 'release': '2.fc7',
    #             'tag_name': 'dist-fc7-updates-testing', 'version': '1.0.2.3'},
    #    ]

    #    testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
    #    self.save_update(params, session)
    #    DevBuildsys.getBuild = oldGetBuild
    #    DevBuildsys.listTagged = oldListTagged
    #    assert 'Broken update path: TurboGears-1.0.2.2-2.fc7 is older than TurboGears-1.0.2.3-2.fc7 in dist-rawhide' in testutil.get_log()

    #def test_broken_update_path_on_request(self):
    #    """ Make sure we are unable to break upgrade paths upon request
    #        https://bugzilla.redhat.com/show_bug.cgi?id=448861
    #    """
    #    from bodhi.buildsys import get_session
    #    koji = get_session()
    #    session = login()
    #    create_release()
    #    params = {
    #        'builds'  : 'TurboGears-1.0.2.2-2.fc7',
    #        'release' : 'Fedora 7',
    #        'type_'    : 'bugfix',
    #        'bugs'    : '',
    #        'cves'    : '',
    #        'notes'   : 'foo'
    #    }
    #    self.save_update(params, session)

    #    # Monkey-patch our DevBuildsys
    #    from bodhi.buildsys import DevBuildsys
    #    oldGetBuild = DevBuildsys.getBuild
    #    DevBuildsys.getBuild = lambda *x, **y: {
    #            'epoch': None, 'name': 'TurboGears',
    #            'nvr': 'TurboGears-1.0.2.2-2.fc7',
    #            'release': '2.fc7',
    #            'tag_name': 'dist-fc7-updates-testing',
    #            'version': '1.0.2.2'
    #            }

    #    # Make a newer build already exist
    #    oldListTagged = koji.listTagged
    #    DevBuildsys.listTagged = lambda *x, **y: [
    #            {'epoch': None, 'name': 'TurboGears',
    #             'nvr': 'TurboGears-1.0.2.3-2.fc7', 'release': '2.fc7',
    #             'tag_name': 'dist-fc7-updates-testing', 'version': '1.0.2.3'},
    #    ]

    #    testutil.capture_log(['bodhi.util', 'bodhi.controllers', 'bodhi.model'])
    #    testutil.create_request('/updates/request/stable/%s' % params['builds'],
    #                           method='POST', headers=session)
    #    DevBuildsys.getBuild = oldGetBuild
    #    DevBuildsys.listTagged = oldListTagged
    #    output = testutil.get_log()
    #    assert 'Broken update path: TurboGears-1.0.2.3-2.fc7 is already released, and is newer than TurboGears-1.0.2.2-2.fc7' in output, output

    # Disabled for now, since we want to try and avoid as much bugzilla
    # contact during our test cases as possible :)
    # We could probably put some sort of facade in place that can handle this
    # case like we did with the buildsys module.
    #def test_cve_bugs(self):
    #    session = login()
    #    create_release()
    #    params = {
    #            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
    #            'release' : 'Fedora 7',
    #            'type'    : 'enhancement',
    #            'bugs'    : 'CVE-2007-5201',
    #            'cves'    : '',
    #            'notes'   : ''
    #    }
    #    self.save_update(params, session)
    #    update = PackageUpdate.byTitle(params['builds'])
    #    assert update.bugs[0].bz_id == 293081
    #    #assert update.bugs[0].title == "CVE-2007-5201 Duplicity discloses password in FTP backend"

    def test_not_owner(self):
        session = login(username='guest')
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '',
                'cves'    : '',
                'notes'   : 'foo'
        }
        self.save_update(params, session)
        assert "This resource resides temporarily" in cherrypy.response.body[0], cherrypy.response.body[0]

    def test_obsoleting(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar',
                'request' : None
        }
        self.save_update(params, session)
        print cherrypy.response.body[0]
        assert "This resource resides temporarily at <a href='http://localhost/updates/TurboGears-1.0.2.2-2.fc7'>http://localhost/updates/TurboGears-1.0.2.2-2.fc7</a>" in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'

        # Throw a newer build in, which should obsolete the previous
        newparams = {
                'builds'  : 'TurboGears-1.0.2.2-3.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '4321',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'bizbaz'
        }
        self.save_update(newparams, session)
        newupdate = PackageUpdate.byTitle(newparams['builds'])
        assert newupdate.status == 'pending'
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'obsolete'

        # The newer build should also inherit the obsolete updates bugs
        bugz = [bug.bz_id for bug in newupdate.bugs]
        assert 1234 in bugz and 4321 in bugz

        # The newer update should also inherit the obsolete updates notes
        assert newupdate.notes == "%s\n%s" % (newparams['notes'], params['notes'])

    def test_obsoleting_multibuild_update(self):
        """ Ensure that a new update cannot obsolete an older update that
        contains this new build along with others """
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlalchemy-0.5-0-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar',
                'request' : None
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))
        assert update.status == 'pending'
        assert len(update.builds) == 2
        assert len(update.builds[0].updates) == 1
        update.status = 'testing'
        update.pushed = True
        update.date_pushed = datetime.now()

        # Throw a newer build in, which should *NOT* obsolete the previous
        newparams = {
                'builds'  : 'python-sqlalchemy-0.5.1-1.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '',
                'cves'    : '',
                'notes'   : 'foo'
        }
        self.save_update(newparams, session)
        newupdate = PackageUpdate.byTitle(newparams['builds'])
        assert newupdate.status == 'pending'
        assert newupdate.notes == 'foo', newupdate.notes
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))
        assert update.status == 'testing', update.status

    def test_obsoleting_update_with_different_packages(self):
        """ Ensure that a new update cannot obsolete an older update that
        contains a different package """
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlalchemy-0.5.0-1.fc7 nethack-1.0-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar',
                'request' : None
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))
        assert update.status == 'pending'
        assert len(update.builds) == 3
        assert len(update.builds[0].updates) == 1
        update.status = 'testing'
        update.pushed = True
        update.date_pushed = datetime.now()

        # Throw a newer build in, which should *NOT* obsolete the previous
        newparams = {
                'builds'  : 'TurboGears-1.0.3.2-2.fc7 python-sqlalchemy-0.6.0-1.fc7 kernel-3.0-1.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '',
                'cves'    : '',
                'notes'   : 'foo'
        }
        #testutil.capture_log(['bodhi.model', 'bodhi.controllers', 'bodhi.admin', 'bodhi.masher', 'bodhi.util'])
        self.save_update(newparams, session)
        #assert False, testutil.get_log()
        newupdate = PackageUpdate.byTitle(','.join(newparams['builds'].split()))
        assert newupdate.status == 'pending'
        assert newupdate.notes == 'foo', newupdate.notes

        # Ensure the original update is still in tact
        update = PackageUpdate.byTitle(','.join(params['builds'].split()))
        assert update.status == 'testing', update.status

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
                'type_'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : '',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)

        url = '/updates/list?' + urllib.urlencode({ 'release' : 'F7' })
        testutil.create_request(url, method='GET')
        assert "1 update found" in cherrypy.response.body[0], cherrypy.response.body[0]

        url = '/updates/list?' + urllib.urlencode({
                'release' : 'F7',
                'bugs'    : '1234'
        })
        testutil.create_request(url, method='GET')
        assert "1 update found" in cherrypy.response.body[0], cherrypy.response.body

        url = '/updates/list?' + urllib.urlencode({
                'release' : 'F7',
                'bugs'    : '1234',
                'type_'    : 'enhancement'
        })
        testutil.create_request(url, method='GET')
        assert "1 update found" in cherrypy.response.body[0]

        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '321',
                'cves'    : '',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)

        # Test querying by updateid
        up = PackageUpdate.byTitle(params['builds'])
        up.assign_id()
        url = '/updates/list?' + urllib.urlencode({
                'package'    : up.updateid
        })
        testutil.create_request(url, method='GET')
        assert "1 update found" in cherrypy.response.body[0]

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
                'type_'   : 'enhancement',
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
                'type_'   : 'enhancement',
                'bugs'    : '321',
                'cves'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        params = {
                'builds'  : 'nethack-2.10-3.20070831cvs.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'enhancement',
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
                'type_'   : 'enhancement',
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
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'testing'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        assert not update.approved

        url = '/updates/approve?update=' + params['builds']
        testutil.create_request(url, headers=session, method='POST')
        update = PackageUpdate.byTitle(params['builds'])
        assert update.approved
        assert update.request == 'testing'

    def test_security_approval_to_stable(self):
        """
        Make sure we disallow pushing directly to stable after security approval
        """
        session = login(group='security_respons')
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'stable',
                'autokarma': False,
        }
        #testutil.capture_log(['bodhi.model', 'bodhi.controllers', 'bodhi.admin', 'bodhi.masher', 'bodhi.util'])
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        #assert False, testutil.get_log()
        assert update.request == 'testing', update.request
        assert not update.approved

        url = '/updates/approve?update=' + params['builds']
        testutil.create_request(url, headers=session, method='POST')
        update = PackageUpdate.byTitle(params['builds'])
        assert update.approved
        assert update.request == 'testing', update.request

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
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable'
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert 'guest' in update.builds[0].package.committers

    def test_karma_thresholds(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'autokarma' : True,
                'stable_karma' : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.stable_karma == 5, update.stable_karma
        assert update.unstable_karma == -5, update.unstable_karma

        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7 python-sqlobject-1.2-3.fc7',
                'edited'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'autokarma' : True,
                'stable_karma' : 1,
                'unstable_karma' : -1,
        }
        #testutil.capture_log(['bodhi.controller', 'bodhi.util'])
        self.save_update(params, session)
        #print testutil.get_log()
        update = PackageUpdate.byTitle(params['builds'].replace(' ', ','))
        assert update.stable_karma == params['stable_karma'], update.stable_karma
        assert update.unstable_karma == params['unstable_karma'], update.unstable_karma

        # Create a different update to ensure we have unique thresholds
        params = {
                'builds'  : 'TurboGears-3.0-1.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'autokarma' : True,
                'stable_karma' : 7,
                'unstable_karma' : -7
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.stable_karma == 7, update.stable_karma
        assert update.unstable_karma == -7, update.unstable_karma

    def test_bad_karma_thresholds(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foo',
                'request' : 'Stable',
                'stable_karma' : 1,
                'unstable_karma' : 2,
                'autokarma': True,
        }
        testutil.capture_log('bodhi.util')
        self.save_update(params, session)
        assert "Stable karma must be higher than unstable karma." in testutil.get_log()

        params['stable_karma'] = 0
        testutil.capture_log('bodhi.util')
        self.save_update(params, session)
        assert "Stable karma must be at least 1." in testutil.get_log()

    def test_anonymous_captcha(self):
        """ Make sure our captcha does its job """
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'stable_karma' : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        testutil.create_request('/updates/captcha_comment?text=bizbaz&title=%s&author=bobvila&karma=-1' %
                                params['builds'], method='POST')
        assert 'An email address must contain a single @' in cherrypy.response.body[0]

        testutil.create_request('/updates/captcha_comment?text=bizbaz&title=%s&author=bob@vila.com&karma=-1' %
                                params['builds'], method='POST')
        assert 'Problem with captcha: Please enter a value' in cherrypy.response.body[0]

        x = testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                   params['builds'], method='POST')
        assert 'You must provide your credentials before accessing this resource.' in cherrypy.response.body[0]

    def test_newpackage_update(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'newpackage',
                'bugs'    : '',
                'notes'   : 'Initial release of new package!',
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.type == 'newpackage'

    def test_admin_push(self):
        session = login(username='admin', group='releng')
        me = User.by_user_name('admin')
        testers = Group(group_name='proventesters', display_name='proventesters')
        me.addGroup(testers)
        create_release()
        testutil.create_request('/updates/admin/push', headers=session)
        assert '0 pending requests' in cherrypy.response.body[0]
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'Initial release of new package!',
                'request' : 'stable'
        }

        self.save_update(params, session)
        assert PackageUpdate.select().count() == 1
        assert PackageUpdate.select()[0].request == 'testing'
        testutil.create_request('/updates/admin/push', headers=session)

        # Make sure security updates do not slip in unapproved
        #assert '0 pending requests' in cherrypy.response.body[0], cherrypy.response.body[0]

        # We no longer require security approval
        assert '1 pending requests' in cherrypy.response.body[0], cherrypy.response.body[0]

        # approve the update
        me = User.by_user_name('admin')
        secteam = Group(group_name='security_respons', display_name='h4x0rs')
        me.addGroup(secteam)
        testutil.create_request('/updates/approve/%s' % params['builds'],
                                headers=session)

        # It should now appear in the queue
        config.update({'global': {'masher': None}})
        #testutil.capture_log(['bodhi.controllers', 'bodhi.admin', 'bodhi.masher', 'bodhi.util'])
        testutil.create_request('/updates/admin/push', headers=session)
        #testutil.print_log()
        assert '1 pending request' in cherrypy.response.body[0], cherrypy.response.body[0]

        # Revoke the testingrequest from the update
        testutil.create_request('/updates/revoke/%s' % params['builds'],
                                headers=session)

        # It should be removed from the queue
        testutil.create_request('/updates/admin/push', headers=session)
        assert '0 pending requests' in cherrypy.response.body[0]

        # Create a MASHING lock with this update in it
        config.update({'global': {'mashed_dir': os.getcwd()}})
        mash_lock = file(os.path.join(config.get('mashed_dir'), 'MASHING-FEDORA'), 'w')
        mash_lock.write(pickle.dumps({'updates': [params['builds'],], 'repos': []}))
        mash_lock.close()

        # Make sure it attempts to resume the current push
        # It should now appear in the queue
        testutil.create_request('/updates/admin/push', headers=session)
        assert '1 pending request' in cherrypy.response.body[0], cherrypy.response.body[0]

    def test_request_comments(self):
        """ Make sure that setting requests also adds comments """
        session = login()
        create_release()
        params = { 'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'newpackage',
                'bugs'    : '',
                'notes'   : 'Initial release of new package!',
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        assert len(update.comments) == 1
        assert update.comments[0].author == 'bodhi', update.comments[0].author
        assert update.comments[0].karma == 0
        assert update.comments[0].text == 'This update has been submitted for testing by guest. ', update.comments[0].text
        testutil.create_request('/updates/request/stable/%s' %
                                params['builds'], method='POST',
                                headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        assert len(update.comments) == 1
        assert update.get_comments()[-1].text == 'This update has been submitted for testing by guest. '
        testutil.create_request('/updates/request/obsolete/%s' %
                                params['builds'], method='POST',
                                headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        print update
        assert len(update.comments) == 2
        assert update.get_comments()[-1].text == 'This update has been obsoleted'
        assert update.get_comments()[-1].author == 'bodhi'

    #def test_build_inheritance(self):
    #    """ Ensure that build inheritance actually works """
    #    session = login()
    #    create_release()
    #    create_release(num='8', dist='dist-f')
    #    assert Release.select().count() == 2
    #    params = {
    #            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
    #            'release' : 'Fedora 7',
    #            'type_'    : 'newpackage',
    #            'bugs'    : '',
    #            'notes'   : 'Initial release of new package!',
    #            'inheritance' : True,
    #    }
    #    testutil.capture_log(['bodhi.controllers', 'bodhi.util'])
    #    self.save_update(params, session)
    #    assert PackageUpdate.select().count() == 2, cherrypy.response.body[0]
    #    update = PackageUpdate.byTitle(params['builds'])
    #    testutil.print_log()

    def test_edit_obsoletion(self):
        """ Make sure that an update cannot obsolete itself during edit """
        session = login()
        create_release(num='9', dist='dist-f')
        create_release(num='8', dist='dist-f')
        params = {
                'builds'  : u'kdelibs-4.1.0-5.fc9,kdegames-4.1.0-2.fc9,konq-plugins-4.1.0-2.fc9,qt-4.4.1-2.fc9,quarticurve-kwin-theme-0.0-0.5.beta4.fc9,kdepimlibs-4.1.0-2.fc9,kdebase-workspace-4.1.0-8.fc9,akonadi-1.0.0-2.fc9,kde-l10n-4.1.0-2.fc9,kdegraphics-4.1.0-3.fc9,kdeutils-4.1.0-1.fc9,kdebindings-4.1.0-5.fc9,kde-i18n-3.5.9-8.fc9,kdeartwork-4.1.0-1.fc9,kdemultimedia-4.1.0-1.fc9,kdetoys-4.1.0-1.fc9,kdebase-runtime-4.1.0-1.fc9,kdeadmin-4.1.0-2.fc9,kdenetwork-4.1.0-2.fc9,kdeaccessibility-4.1.0-1.fc9,kdeplasma-addons-4.1.0-1.fc9,kdeedu-4.1.0-1.fc9,kdebase-4.1.0-1.fc9,kdesdk-4.1.0-1.fc9,kde-filesystem-4-17.fc9,qscintilla-2.2-3.fc9,qgtkstyle-0.0-0.2.20080719svn693.fc9,compiz-0.7.6-3.fc9,soprano-2.1-1.fc9,PyQt4-4.4.2-2.fc9,sip-4.7.6-1.fc9,automoc-1.0-0.8.rc1.fc9,phonon-4.2.0-2.fc9',
                'type_'   : 'enhancement',
                'bugs'    : u'457526 456820 454930 454458 456827 456797 456850 440226 455623 440031 453321 457479 457739',
                'notes'   : u'This is an update to kde-4.1.0.  \r\n\r\nSee also:\r\nhttp://www.kde.org/announcements/4.1/\r\n\r\nNOTE: This update does not include kdepim-4.1.0',
        }
        self.save_update(params, session)
        assert PackageUpdate.select().count() == 1
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'
        assert PackageBuild.select().count() == len(params['builds'].split(','))
        update.status = 'testing'
        params = {
                'builds'  : u'kdelibs-4.1.0-5.fc9,kdegames-4.1.0-2.fc9,konq-plugins-4.1.0-2.fc9,qt-4.4.1-2.fc9,quarticurve-kwin-theme-0.0-0.5.beta4.fc9,kdepimlibs-4.1.0-2.fc9,kdebase-workspace-4.1.0-8.fc9,akonadi-1.0.0-2.fc9,kde-l10n-4.1.0-2.fc9,kdegraphics-4.1.0-4.fc9,kdeutils-4.1.0-1.fc9,kdebindings-4.1.0-5.fc9,kde-i18n-3.5.9-8.fc9,kdeartwork-4.1.0-1.fc9,kdemultimedia-4.1.0-1.fc9,kdetoys-4.1.0-1.fc9,kdebase-runtime-4.1.0-3.fc9,kdeadmin-4.1.0-2.fc9,kdenetwork-4.1.0-2.fc9,kdeaccessibility-4.1.0-1.fc9,kdeplasma-addons-4.1.0-1.fc9,kdeedu-4.1.0-1.fc9,kdebase-4.1.0-1.fc9,kdesdk-4.1.0-1.fc9,kde-filesystem-4-17.fc9,qscintilla-2.2-3.fc9,qgtkstyle-0.0-0.2.20080719svn693.fc9,compiz-0.7.6-3.fc9,soprano-2.1-1.fc9,PyQt4-4.4.2-2.fc9,sip-4.7.6-1.fc9,automoc-1.0-0.8.rc1.fc9,phonon-4.2.0-4.fc9',
                'release' : 'Fedora 7',
                'type_'   : 'enhancement',
                'bugs'    : '',
                'notes'   : 'foo',
                'edited'  : u'kdelibs-4.1.0-5.fc9,kdegames-4.1.0-2.fc9,konq-plugins-4.1.0-2.fc9,qt-4.4.1-2.fc9,quarticurve-kwin-theme-0.0-0.5.beta4.fc9,kdepimlibs-4.1.0-2.fc9,kdebase-workspace-4.1.0-8.fc9,akonadi-1.0.0-2.fc9,kde-l10n-4.1.0-2.fc9,kdegraphics-4.1.0-3.fc9,kdeutils-4.1.0-1.fc9,kdebindings-4.1.0-5.fc9,kde-i18n-3.5.9-8.fc9,kdeartwork-4.1.0-1.fc9,kdemultimedia-4.1.0-1.fc9,kdetoys-4.1.0-1.fc9,kdebase-runtime-4.1.0-1.fc9,kdeadmin-4.1.0-2.fc9,kdenetwork-4.1.0-2.fc9,kdeaccessibility-4.1.0-1.fc9,kdeplasma-addons-4.1.0-1.fc9,kdeedu-4.1.0-1.fc9,kdebase-4.1.0-1.fc9,kdesdk-4.1.0-1.fc9,kde-filesystem-4-17.fc9,qscintilla-2.2-3.fc9,qgtkstyle-0.0-0.2.20080719svn693.fc9,compiz-0.7.6-3.fc9,soprano-2.1-1.fc9,PyQt4-4.4.2-2.fc9,sip-4.7.6-1.fc9,automoc-1.0-0.8.rc1.fc9,phonon-4.2.0-2.fc9',
        }
        #testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        #testutil.print_log()
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'
        assert PackageUpdate.select().count() == 1
        assert PackageBuild.select().count() == len(params['builds'].split(','))

    def test_revoke_request(self):
        session = login()
        create_release(num='8', dist='dist-f')
        params = {
                'builds'  : u'TurboGears-1.0.7-1.fc8',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foo',
        }
        #testutil.capture_log(['bodhi.controllers', 'bodhi.util'])
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        testutil.create_request('/updates/request/revoke/%s' % params['builds'],
                                headers=session, method='POST')
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == None

    def test_unicode_fail(self):
        session = login()
        create_release(num='8', dist='dist-f')
        params = {'stable_karma': 3,
                'builds': 'pidgin-libnotify-0.14-1.fc8',
                'autokarma': True,
                'inheritance': False,
                'suggest_reboot': False,
                'notes': u"Version 0.14 (2008-12-14):\r\n\r\n    * really add option: don't show notifications when absent\r\n    * Updated polish translation (Piotr Dr\u0105g)\r\n    * Added russian translation (Dmitry Egorkin)\r\n    * Added bulgarian translation (Dilyan Palauzov)\r\n    * Added german translation (Marc Mikolits)\r\n    * Added swedish translation (Jonas Granqvist)\r\n".encode('utf8'),
                'request': u'Testing',
                'bugs': '477267',
                'unstable_karma': -3,
                'type_': u'bugfix',
                'close_bugs': True}
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update

    def test_get_updates_from_builds(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '1234',
                'cves'    : 'CVE-2020-0001',
                'notes'   : 'foobar'
        }
        self.save_update(params, session)
        params = {
                'builds'  : 'kernel-2.6.29.1-111.fc7.x86_64',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '1234',
                'notes'   : 'New kernel.'
        }
        self.save_update(params, session)
        testutil.create_request('/updates/get_updates_from_builds?builds=' +
                'kernel-2.6.29.1-111.fc7.x86_64%20TurboGears-1.0.2.2-2.fc7',
                method='POST')
        json = simplejson.loads(cherrypy.response.body[0])
        assert 'kernel-2.6.29.1-111.fc7.x86_64' in json
        assert 'TurboGears-1.0.2.2-2.fc7' in json
        assert json['TurboGears-1.0.2.2-2.fc7']['notes'] == 'foobar'

    def test_updating_build_during_edit(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : None,
                'stable_karma' : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        update.status = 'testing'
        update.date_pushed = datetime.now()
        update.pushed = True

        params = {
                'builds'  : 'TurboGears-2.6.24-1.fc7',
                'edited'  : 'TurboGears-2.6.23.1-21.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.status == 'pending'
        assert update.request == 'testing'
        assert update.title == 'TurboGears-2.6.24-1.fc7'
        assert len(update.builds) == 1
        assert update.builds[0].nvr == 'TurboGears-2.6.24-1.fc7'
        try:
            b = PackageBuild.byNvr('TurboGears-2.6.23.1-21.fc7')
            assert False, "Old obsolete build still exists!!"
        except SQLObjectNotFound:
            pass

    def test_push_untested_critpath_to_release(self):
        """
        Ensure that we cannot push an untested critpath update directly to
        stable.
        """
        session = login()
        create_release()
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': 'stable',
                'unstable_karma' : -1,
        }
        testutil.capture_log(["bodhi.util", "bodhi.controllers", "bodhi.model"])
        self.save_update(params, session)
        log = testutil.get_log()
        assert "Forcing critical path update into testing" in log, log
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'

    def test_critpath_actions_in_normal_release(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == None

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)
        assert "Push to Stable" not in cherrypy.response.body[0]
        assert "Push to Testing" in cherrypy.response.body[0]

        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='GET', headers=session)
        update = PackageUpdate.byTitle(params['builds'])

        # We're no longer allowing devs to request critpath updates to stable
        # without a karma prerequisite for non-pending releases.
        # This feature can be disabled by setting
        #`critpath.num_admin_approvals = 0` in your configuration
        assert update.request == 'testing', update.request
        #assert update.karma == 1, update.karma

    def test_non_critpath_actions_in_normal_release(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'nethack-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == None

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)
        assert "Push to Testing" in cherrypy.response.body[0]
        assert "Push to Stable" in cherrypy.response.body[0], cherrypy.response.body[0]

    def test_push_critpath_to_frozen_release(self):
        session = login()
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': 'stable',
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'

        # Ensure we can't create a stable request
        testutil.capture_log(["bodhi.util", "bodhi.controllers", "bodhi.model"])
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='POST', headers=session)
        log = testutil.get_log()
        assert "Forcing critical path update into testing" in log
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'

    def test_push_critpath_to_frozen_release_and_request_stable_as_releng(self):
        session = login(group='proventesters')
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': 'stable',
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'

        # Ensure we can't create a stable request
        testutil.capture_log(["bodhi.util", "bodhi.controllers", "bodhi.model"])
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        log = testutil.get_log()
        assert "Forcing critical path update into testing" in log, log
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'

    def test_critpath_to_frozen_release_available_actions(self):
        """
        Ensure devs can attempt to push critpath updates for pending releases
        to stable, but make sure that it can only go to testing.
        """
        session = login()
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)

        assert "Push to Testing" in cherrypy.response.body[0]
        assert "Push to Stable" not in cherrypy.response.body[0]

        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'

    def test_critpath_with_autokarma_disabled(self):
        """
        Ensure that people can still disable karma automatism with critpath
        updates.
        """
        releng = login(group='proventesters')
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'autokarma': False,
                'stable_karma' : 10,
                'request': None,
                'unstable_karma' : -10,
        }
        self.save_update(params, releng)
        update = PackageUpdate.byTitle(params['builds'])
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=releng)

        # Ensure releng/QA can't push critpath updates alone
        assert "Push to Testing" in cherrypy.response.body[0]
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]

        # Have a developer +1 the update
        developer = login(username='bob')
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=developer)
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=developer)
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert not update.request
        assert len(update.comments) == 1
        assert update.comments[0].author == 'bob'

        # Make sure not even releng can submit it to stable until it gets another
        # approval
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='GET', headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        assert update.karma == 1
        update.request = None

        # Have another developer +1 it, so it gets up to +2
        # Ensure we can't push it to stable, until we get admin approval
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=login(username='foobar'))
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=login(username='foobar'))
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 2
        assert update.request != 'stable', update.request

        # Have releng try again, and ensure it can be pushed to stable
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        print update.stable_karma, update.unstable_karma
        assert update.request == None

    def test_critpath_num_approved_comments_with_autokarma(self):
        """
        Ensure releng/qa can push critpath updates to stable for pending releases
        after 1 releng/qa karma, and 1 other karma
        """
        releng = login(group='proventesters')
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'autokarma': True,
                'stable_karma' : 3,
                'request': None,
                'unstable_karma' : -3,
                'autokarma': True,
        }
        self.save_update(params, releng)
        update = PackageUpdate.byTitle(params['builds'])
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=releng)

        # Ensure releng/QA can't push critpath updates alone
        assert "Push to Testing" in cherrypy.response.body[0]
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]

        # Have a developer +1 the update
        developer = login(username='bob')
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=developer)
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=developer)
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert not update.request
        assert len(update.comments) == 1
        assert update.comments[0].author == 'bob'

        # Make sure not even releng can submit it to stable until it gets another
        # approval
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='GET', headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        assert update.karma == 1
        update.request = None

        # Have another developer +1 it, so it gets up to +2
        # Ensure we can't push it to stable, until we get admin approval
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=login(username='foobar'))
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=login(username='foobar'))
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 2
        assert update.request != 'stable', update.request

        # Have releng try again, and ensure it can be pushed to stable
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=login('otherguy'))
        update = PackageUpdate.byTitle(params['builds'])
        print update.stable_karma, update.unstable_karma
        assert update.request == 'stable', update.request

        # Reset it
        update.request = None

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=developer)
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        print update.comments
        assert "Push Critical Path update to Stable" in cherrypy.response.body[0]

        testutil.create_request('/updates/request/stable/%s' %
                                params['builds'], method='POST',
                                headers=releng)

        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable'

    def test_critpath_num_approved_comments_with_high_stable_threshold(self):
        """
        Ensure releng/qa can push critpath updates to stable
        after 1 releng/qa karma, and 1 other karma -- but ensure that
        it doesn't get pushed to stable automatically because it has yet to
        reach the stable_karma threshold.
        """
        releng = login(group='proventesters')
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'autokarma': True,
                'stable_karma' : 10,
                'request': None,
                'unstable_karma' : -10,
                'autokarma': True,
        }
        self.save_update(params, releng)
        update = PackageUpdate.byTitle(params['builds'])
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=releng)

        # Ensure releng/QA can't push critpath updates alone
        assert "Push to Testing" in cherrypy.response.body[0]
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]

        # Have a developer +1 the update
        developer = login(username='bob')
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=developer)
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=developer)
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert not update.request
        assert len(update.comments) == 1
        assert update.comments[0].author == 'bob'

        # Make sure not even releng can submit it to stable until it gets another
        # approval
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='GET', headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing'
        assert update.karma == 1
        update.request = None

        # Have another developer +1 it, so it gets up to +2
        # Ensure we can't push it to stable, until we get admin approval
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=login(username='foobar'))
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=login(username='foobar'))
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 2
        assert update.request != 'stable', update.request

        # Have releng try again, and ensure it can be pushed to stable
        #testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=login('otherguy'))
        update = PackageUpdate.byTitle(params['builds'])
        print update.stable_karma, update.unstable_karma

        assert update.request == None, "Auto-karma kicked in even though it didn't reach the stable threshold yet!"

        assert update.critpath
        assert update.critpath_approved

        # 7 more comments
        for user in range(7):
            dev_user = login(username='user%d' % user)
            testutil.create_request('/updates/comment?text=yay&title=%s&karma=1'
                                    % params['builds'], method='POST',
                                    headers=dev_user)

        update = PackageUpdate.byTitle(params['builds'])
        #logs = testutil.get_log()
        #print logs
        #assert False, logs
        assert update.request == 'stable', update.__json__()

    def test_critpath_to_frozen_release_testing(self):
        """
        Ensure devs can *not* push critpath updates directly to stable
        for pending releases
        """
        session = login()
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Pretend it's pushed to testing
        update.pushed = True
        update.status = 'testing'

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)

        # Ensure the dev cannot push it to stable
        assert "/updates/request/stable" not in cherrypy.response.body[0]

    def test_non_critpath_to_frozen_release_testing(self):
        """
        Ensure non-critpath packages can still be pushed to stable as usual
        """
        session = login()
        create_release(locked=True)
        params = {
                'builds'  : 'nethack-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)

        assert "/updates/request/stable" in cherrypy.response.body[0], cherrypy.response.body[0]
        # Pretend it's pushed to testing
        update.pushed = True
        update.status = 'testing'

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)

        assert "/updates/request/stable" in cherrypy.response.body[0], cherrypy.response.body[0]

    def test_critpath_to_frozen_release_testing_admin_actions(self):
        """
        Ensure admins can submit critpath updates for pending releases to stable.
        """
        session = login(group='proventesters')
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
                'autokarma': True,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Pretend it's pushed to testing
        update.pushed = True
        update.status = 'testing'

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)

        assert "Mark Critical Path update as Stable" not in cherrypy.response.body[0]

        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=login('otherguy'))

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)

        assert "Mark Critical Path update as Stable" not in cherrypy.response.body[0]

        #testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=login(username='bob'))

        update = PackageUpdate.byTitle(params['builds'])
        assert update.critpath
        assert update.critpath_approved
        #assert False, testutil.get_log()
        assert len(update.comments) == 4, update.comments
        assert update.comments[-1].author == 'bodhi', update.comments
        assert update.comments[-1].text == config.get('stablekarma_comment')
        assert update.comments[1].author == 'bob', update.comments
        assert update.comments[-2].author == 'bodhi', update.comments
        assert update.comments[-2].text == 'Critical path update approved'

    def test_critpath_request_complete(self):
        """
        Ensure devs can *not* push critpath updates directly to stable
        for pending releases
        """
        session = login()
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': 'stable',
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.critpath

        update.request_complete()
        assert not update.request

    def test_critpath_two_weeks_without_negative_karma(self):
        """
        Ensure critpath updates can be pushed to stable after two weeks without
        any negative feedback.
        """
        releng = login(group='proventesters')
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'autokarma': True,
                'stable_karma' : 3,
                'request': None,
                'unstable_karma' : -3,
                'autokarma': True,
        }
        self.save_update(params, releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.critpath
        assert not update.critpath_approved
        #
        # Give some positive karma
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                            params['builds'], method='POST', headers=releng)

        # Ensure releng/QA can't push critpath updates alone
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=releng)
        assert "Push to Testing" in cherrypy.response.body[0]
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        testutil.create_request('/updates/request/stable/%s' %
                                params['builds'], method='POST',
                                headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing', update.request

        assert not update.critpath_approved
        assert not update.meets_testing_requirements

        # Time travel
        update.pushed = True
        update.request = None
        update.status = 'testing'
        update.status_comment()
        update.comments[-1].timestamp -= timedelta(days=14)

        assert update.meets_testing_requirements
        assert update.critpath_approved

        # Ensure it can now be pushed
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=releng)
        assert "Mark Critical Path update as Stable" in cherrypy.response.body[0]

        testutil.create_request('/updates/request/stable/%s' %
                                params['builds'], method='POST',
                                headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable', update.request

    def test_critpath_two_weeks_with_negative_karma(self):
        """
        Ensure critpath updates cannot be pushed to stable after two weeks with
        negative feedback.
        """
        releng = login(group='proventesters')
        create_release(locked=True)
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'autokarma': True,
                'stable_karma' : 3,
                'request': None,
                'unstable_karma' : -3,
                'autokarma': True,
        }
        self.save_update(params, releng)
        update = PackageUpdate.byTitle(params['builds'])
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=releng)

        # Ensure releng/QA can't push critpath updates alone
        assert "Push to Testing" in cherrypy.response.body[0]
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        testutil.create_request('/updates/request/stable/%s' %
                                params['builds'], method='POST',
                                headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing', update.request

        # Time travel
        update.pushed = True
        update.request = None
        update.status = 'testing'
        update.status_comment()
        update.comments[-1].timestamp -= timedelta(days=14)

        # Give some negative karma
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=-1' %
                                params['builds'], method='POST',
                                headers=login('otherguy'))

        # Ensure it cannot now be pushed
        testutil.create_request('/updates/request/stable/%s' %
                                params['builds'], method='POST',
                                headers=releng)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request != 'stable', update.request

    def test_critpath_without_proventesters(self):
        """
        Ensure critpath updates can still go to stable without proventesters.
        https://fedorahosted.org/bodhi/ticket/653
        """
        session = login()
        create_release()
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
                'autokarma': True
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == None

        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=session)
        assert "Push to Stable" not in cherrypy.response.body[0]
        assert "Push to Testing" in cherrypy.response.body[0]

        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='GET', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 0

        # We're no longer allowing devs to request critpath updates to stable
        # without a karma prerequisite for non-pending releases.
        # This feature can be disabled by setting
        #`critpath.num_admin_approvals = 0` in your configuration
        assert update.request == 'testing', update.request

        # Have a user +1 the update
        developer = login(username='bob')
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=login('otherguy'))
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=developer)
        assert "Push Critical Path update to Stable" not in cherrypy.response.body[0]
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                                method='GET', headers=session)

        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 1
        assert update.request == 'testing', update.request

        # Have a developer +1 the update
        developer = login(username='bob')
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=developer)
        testutil.create_request('/updates/%s' % params['builds'],
                                method='GET', headers=developer)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 2
        assert update.request == 'stable'

    def test_created_since(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Pretend it's pushed to stable
        update.pushed = True
        update.status = 'stable'
        update.date_submitted = datetime(2010, 01, 01, 12, 00, 00)

        ## Test web UI
        testutil.create_request('/updates/list?%s' %
                urlencode({'created_since': str(update.date_submitted)}),
                method='GET', headers=session)

        assert '1 update found' in cherrypy.response.body[0], cherrypy.response.body[0]
        assert 'kernel-2.6.31-1.fc7' in cherrypy.response.body[0]

        ## Test JSON API
        testutil.create_request('/updates/list?%s' %
                urlencode({'created_since': str(update.date_submitted),
                           'tg_format': 'json'}),
                method='GET', headers=session)

        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 1
        assert json['updates'][0]['title'] == params['builds']

        testutil.create_request('/updates/list?%s' %
                urlencode({
                    'tg_format': 'json',
                    'created_since': str(update.date_submitted +
                                         timedelta(days=1)),
                    }),
                method='GET', headers=session)

        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 0

    def test_modified_since(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        ## Test web UI and make sure it doesn't show up
        testutil.create_request('/updates/list?%s' %
                urlencode({'modified_since': str(update.date_submitted)}),
                method='GET', headers=session)

        assert '1 update found' not in cherrypy.response.body[0], cherrypy.response.body[0]

        # Pretend it has been modified
        update.date_modified = update.date_submitted + timedelta(days=1)

        ## Test web UI to make sure it's there now
        testutil.create_request('/updates/list?%s' %
                urlencode({'modified_since': str(update.date_submitted)}),
                method='GET', headers=session)

        assert '1 update found' in cherrypy.response.body[0], cherrypy.response.body[0]
        assert 'kernel-2.6.31-1.fc7' in cherrypy.response.body[0]

        ## Test JSON API
        testutil.create_request('/updates/list?%s' %
                urlencode({'modified_since': str(update.date_submitted),
                           'tg_format': 'json'}),
                method='GET', headers=session)

        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 1
        assert json['updates'][0]['title'] == params['builds']

        testutil.create_request('/updates/list?%s' %
                urlencode({
                    'tg_format': 'json',
                    'modified_since': str(update.date_submitted +
                                          timedelta(days=2)),
                    }),
                method='GET', headers=session)

        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 0

    def test_pushed_since(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])

        # Pretend it's pushed to stable
        update.pushed = True
        update.status = 'stable'
        update.date_pushed = datetime(2010, 01, 01, 12, 00, 00)

        ## Test web UI
        testutil.create_request('/updates/list?%s' %
                urlencode({'pushed_since': str(update.date_pushed)}),
                method='GET', headers=session)

        assert '1 update found' in cherrypy.response.body[0]
        assert 'kernel-2.6.31-1.fc7' in cherrypy.response.body[0]

        ## Test JSON API
        testutil.create_request('/updates/list?%s' %
                urlencode({'pushed_since': str(update.date_pushed),
                           'tg_format': 'json'}),
                method='GET', headers=session)

        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 1
        assert json['updates'][0]['title'] == params['builds']

        testutil.create_request('/updates/list?%s' %
                urlencode({
                    'tg_format': 'json',
                    'pushed_since': str(update.date_pushed + timedelta(days=1)),
                    }),
                method='GET', headers=session)

        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 0

    def test_query_limit(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'kernel-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': None,
                'unstable_karma' : -1,
        }
        #update = PackageUpdate.byTitle(params['builds'])

        # Create 100 updates
        for prefix in xrange(100):
            update = params.copy()
            update['builds'] = '%s%d%s' % (update['builds'][0], prefix,
                                           update['builds'][1:])
            self.save_update(update, session)

        assert PackageUpdate.select().count() == 100, PackageUpdate.select().count()

        ## Test default limit
        testutil.create_request('/updates/list?tg_format=json', method='GET',
                                headers=session)

        assert '100 updates found' in cherrypy.response.body[0], cherrypy.response.body[0]
        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 100, json['num_items']
        assert len(json['updates']) == 25, len(json['updates'])

        ## Try getting all 100
        testutil.create_request('/updates/list?tg_format=json&updates_tgp_limit=100',
                                method='GET', headers=session)

        assert '100 updates found' in cherrypy.response.body[0], cherrypy.response.body[0]
        json = simplejson.loads(cherrypy.response.body[0])
        assert json['num_items'] == 100, json['num_items']
        assert len(json['updates']) == 100, len(json['updates'])

    def test_add_bugs_to_update(self):
        session = login()
        f7 = create_release()
        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'type_'   : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
            'notes'   : 'foo'
        }
        self.save_update(params, session)

        params = {
            'builds'  : 'TurboGears-1.0.2.2-2.fc7 python-sqlobject-0.8.2-1.fc7',
            'release' : 'Fedora 7',
            'type_'   : 'bugfix',
            'bugs'    : '1 2',
            'cves'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.2.2-2.fc7,python-sqlobject-0.8.2-1.fc7',
        }

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()
        assert 'Updating newly added bug: 2' in logs
        assert len(PackageUpdate.byTitle(params['edited']).bugs) == 2

    def test_metrics_api(self):
        release = create_release()
        refresh_metrics()
        testutil.create_request('/updates/metrics/?tg_format=json', method='GET')
        response = simplejson.loads(cherrypy.response.body[0])
        assert 'F7' in response
        print response
        assert response['F7']['TopTestersMetric']['data'] == [], response

    def test_metrics_html(self):
        release = create_release()
        refresh_metrics()
        testutil.create_request('/updates/metrics/', method='GET')
        assert 'flot' in cherrypy.response.body[0]

    def test_bullets(self):
        session = login()
        f7 = create_release()
        params = {
            'notes'   : '\xc2\xb7',
            'builds'  : 'TurboGears-1.0.2.2-2.fc7',
            'type_'   : 'bugfix',
            'bugs'    : '1',
            'cves'    : '',
        }
        #testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        #logs = testutil.get_log()
        #assert False, logs
        update = PackageUpdate.byTitle(params['builds'])
        assert update.notes == u'\xb7'
        assert update.notes.encode('utf-8') == '\xc2\xb7'
        testutil.create_request('/updates/' + params['builds'])
        body  = cherrypy.response.body[0]
        assert '\xc2\xb7' in body
        assert u'·' in body.decode('utf-8')

        # Try throwing it at the root controller directly
        #testutil.set_identity_user(User.select()[0])
        #try:
        #    testutil.call(cherrypy.root.save, **{'stable_karma': 3, 'edited': False, 'builds': [u'TurboGears2-2.0.3-1.fc7'], 'autokarma': False, 'inheritance': False, 'suggest_reboot': False, 'notes': u'\xb7', 'bugs': '1', 'unstable_karma': -3, 'type_': u'bugfix', 'close_bugs': False})
        #except cherrypy._cperror.HTTPRedirect, e:
        #    assert e.status == 303
        #    assert e.urls[0] == u'/updates/TurboGears2-2.0.3-1.fc7'

    def test_karma_change(self):
        """
        Ensure that a developer can give negative karma, and then proceed to
        later give positive karma.
        """
        session = login()
        other_session = login('otherguy')
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.8-1.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'autokarma' : True,
                'stable_karma' : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)
        assert PackageUpdate.byTitle(params['builds']).karma == 0

        dev1 = login(username='bob')
        testutil.create_request('/updates/comment?text=bar&title=%s&karma=1' %
                                params['builds'], method='POST', headers=dev1)
        up = PackageUpdate.byTitle(params['builds'])
        assert up.karma == 1

        dev2 = login(username='jim')
        testutil.create_request('/updates/comment?text=biz&title=%s&karma=1' %
                                params['builds'], method='POST', headers=dev2)
        assert PackageUpdate.byTitle(params['builds']).karma == 2

        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=-1' %
                                params['builds'], method='POST',
                                headers=other_session)
        assert PackageUpdate.byTitle(params['builds']).karma == 1

        # Give a bunch of +0's
        testutil.create_request('/updates/comment?text=blah&title=%s&karma=0' %
                                params['builds'], method='POST', headers=dev1)
        assert PackageUpdate.byTitle(params['builds']).karma == 1
        testutil.create_request('/updates/comment?text=blah&title=%s&karma=0' %
                                params['builds'], method='POST',
                                headers=other_session)
        assert PackageUpdate.byTitle(params['builds']).karma == 1
        testutil.create_request('/updates/comment?text=blah&title=%s&karma=0' %
                                params['builds'], method='POST', headers=dev2)
        assert PackageUpdate.byTitle(params['builds']).karma == 1

        #testutil.capture_log(['bodhi.controller', 'bodhi.util'])
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=other_session)
        up = PackageUpdate.byTitle(params['builds'])
        #assert False, testutil.get_log()
        assert up.karma == 3, up.karma

    def test_reverting_karma(self):
        """
        Ensure that a developer can give negative karma, and then proceed to
        later give positive karma.
        """
        session = login()
        other_session = login('otherguy')
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.8-1.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'autokarma' : True,
                'stable_karma' : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)
        assert PackageUpdate.byTitle(params['builds']).karma == 0

        testutil.create_request('/updates/comment?text=bar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=other_session)
        assert PackageUpdate.byTitle(params['builds']).karma == 1

        testutil.create_request('/updates/comment?text=bar&title=%s&karma=-1' %
                                params['builds'], method='POST',
                                headers=other_session)
        assert PackageUpdate.byTitle(params['builds']).karma == -1

        testutil.create_request('/updates/comment?text=bar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=other_session)
        assert PackageUpdate.byTitle(params['builds']).karma == 1, PackageUpdate.byTitle(params['builds']).karma

    def test_suggest_reboot(self):
        session = login()
        create_release()
        params = {
                'builds'         : 'TurboGears-1.0.8-1.fc7',
                'release'        : 'Fedora 7',
                'type_'          : 'security',
                'bugs'           : '',
                'notes'          : 'foobar',
                'request'        : 'Stable',
                'suggest_reboot' : True,
                'autokarma'      : True,
                'stable_karma'   : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)

        # Ensure the flag gets set properly
        assert PackageUpdate.byTitle(params['builds']).builds[0].package.suggest_reboot

        params = {
                'builds'  : 'TurboGears-1.0.8-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'suggest_reboot': False,
                'autokarma' : True,
                'stable_karma' : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)

        # Ensure the flag gets unset properly
        assert not PackageUpdate.byTitle(params['builds']).builds[0].package.suggest_reboot

    def test_push_critpath_to_EPEL(self):
        session = login()
        rel = Release(name='EL5', long_name='Fedora EPEL 5',
                      id_prefix='FEDORA-EPEL', dist_tag='dist-5E-epel')
        params = {
                'builds'  : 'kernel-2.6.31-1.el5',
                'release' : 'Fedora EPEL 5',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foobar',
                'stable_karma' : 1,
                'request': 'stable',
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing', update.request

    def test_duplicate_packages_for_same_release(self):
        """
        Ensure that bodhi disallows submitting an update with two versions
        of the same package (#264).
        """
        session = login()
        create_release()
        params = {
                'builds'         : 'TurboGears-1.0.8-1.fc7,TurboGears-1.0.8-2.fc7',
                'release'        : 'Fedora 7',
                'type_'          : 'bugfix',
                'bugs'           : '',
                'notes'          : 'foobar',
                'request'        : 'Stable',
                'suggest_reboot' : True,
                'autokarma'      : True,
                'stable_karma'   : 5,
                'unstable_karma' : -5
        }
        testutil.capture_log(['bodhi.controller', 'bodhi.util'])
        self.save_update(params, session)
        log = testutil.get_log()
        assert u'Unable to save update with conflicting builds of the same package: TurboGears-1.0.8-1.fc7 and TurboGears-1.0.8-2.fc7. Please remove one and try again.' in log, log
        try:
            up = PackageUpdate.byTitle(params['builds'])
            assert False, "Update with duplicate packages was saved!"
        except SQLObjectNotFound, e:
            pass

    def test_duplicate_packages_for_different_releases(self):
        """
        Ensure that bodhi allows submitting an update with two versions of the
        same package to different releases.
        """
        session = login()
        create_release()
        create_release('8', dist='dist-f')
        params = {
                'builds'         : 'TurboGears-1.0.8-1.fc7,TurboGears-1.0.8-2.fc8',
                'type_'          : 'bugfix',
                'bugs'           : '',
                'notes'          : 'foobar',
                'request'        : 'Stable',
                'suggest_reboot' : True,
                'autokarma'      : True,
                'stable_karma'   : 5,
                'unstable_karma' : -5
        }
        testutil.capture_log(['bodhi.controller', 'bodhi.util'])
        self.save_update(params, session)
        log = testutil.get_log()
        try:
            up = PackageUpdate.byTitle(params['builds'])
            assert False, "Update created with 2 builds for 2 different releases!"
        except SQLObjectNotFound:
            pass
        one, two = params['builds'].split(',')
        up1 = PackageUpdate.byTitle(one)
        assert up1.title == one
        up2 = PackageUpdate.byTitle(two)
        assert up2.title == two

    def test_week_in_testing(self):
        from bodhi.jobs import approve_testing_updates
        session = login()
        create_release()
        params = {
            'builds'         : 'TurboGears-1.0.8-1.fc7',
            'release'        : 'Fedora 7',
            'type_'          : 'bugfix',
            'bugs'           : '',
            'notes'          : 'foobar',
            'request'        : 'Stable',
            'suggest_reboot' : True,
            'autokarma'      : True,
            'stable_karma'   : 5,
            'unstable_karma' : -5
        }
        self.save_update(params, session)
        up = PackageUpdate.byTitle(params['builds'])

        # Ensure we can't push directly to stable
        assert up.request == 'testing'

        # Pretend it's pushed to testing
        up.status = 'testing'
        up.status_comment()
        assert not up.days_in_testing

        # Run the approve_testing_updates job, which shouldn't do anything
        approve_testing_updates()

        # Fake almost a week of testing
        assert len(up.comments) == 2, up.comments
        up.comments[1].timestamp -= timedelta(days=6)
        assert up.days_in_testing == 6

        # Run the approve_testing_updates job, which shouldn't do anything
        approve_testing_updates()

        # Ensure it can't be pushed, and that there are no comments
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        up = PackageUpdate.byTitle(params['builds'])
        assert not up.request
        assert len(up.comments) == 2, up.comments[-1].text

        # Fake a week of testing
        up.comments[0].timestamp -= timedelta(days=1)
        assert up.days_in_testing == 7, up.days_in_testing

        # Run the approve_testing_updates job, which should approve this update
        approve_testing_updates()

        # assert approval comment in comments
        up = PackageUpdate.byTitle(params['builds'])
        assert len(up.comments) == 3
        assert up.comments[-1].text == 'This update has reached 7 days in testing and can be pushed to stable now if the maintainer wishes'

        # ensure it's not auto pushed to testing
        assert up.status == 'testing'
        assert not up.request

        # ensure we can push it to testing
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        up = PackageUpdate.byTitle(params['builds'])
        assert up.request == 'stable'
        assert up.comments[-1].text == u'This update has been submitted for stable by guest. '

    def test_push_noncritpath_on_critpath_reqs(self):
        """
        Make sure normal updates can meet the testing requirements after
        achieving critpath-level approval.
        """
        session = login(username='admin', group='proventesters')
        create_release()
        f7 = Release.byName('F7')
        assert f7.mandatory_days_in_testing, f7.mandatory_days_in_testing
        params = {
                'builds'  : 'nethack-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foo',
                'autokarma': True,
                'stable_karma' : 3,
                'request': 'stable',
                'unstable_karma' : -3,
        }

        #testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        #logs = testutil.get_log()
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request != 'stable', update.request

        # proventester +1
        testutil.create_request('/updates/comment?text=foobar&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=login('otherguy', group='proventesters'))
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 1
        assert update.request != 'stable'
        assert len(update.comments) == 2
        assert not update.critpath
        assert not update.critpath_approved
        assert update.num_admin_approvals == 1

        # try to push, and fail
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request != 'stable'

        # normal user +1
        testutil.create_request('/updates/comment?text=bizbaz&title=%s&karma=1' %
                                params['builds'], method='POST',
                                headers=login())
        update = PackageUpdate.byTitle(params['builds'])
        assert update.karma == 2, update.karma
        assert update.request != 'stable'
        assert update.num_admin_approvals == 1

        # currently: try to push fail... eventually, succeed
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable'

    def test_obsoleting_different_batches_of_updates(self):
        """
        Make sure a batch of builds can't obsolete an update that only has a
        single build
        """
        session = login()
        create_release()
        params = {
                'builds'  : 'nethack-2.6.31-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foo',
                'autokarma': True,
                'stable_karma' : 3,
                'request': 'stable',
                'unstable_karma' : -3,
        }

        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request != 'stable', update.request
        update.status = 'testing'
        update.pushed = True
        update.request = None
        update.pushed = True

        new_params = {
                'builds'  : 'kernel-2.6.40-1.fc7,nethack-2.6.32-1.fc7,TurboGears-1.2.0-1.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foo',
                'autokarma': True,
                'stable_karma' : 3,
                'request': 'stable',
                'unstable_karma' : -3,
        }
        self.save_update(new_params, session)

        # Make sure it doesn't obsolete the older one
        assert PackageUpdate.byTitle(new_params['builds']).status == 'pending'
        assert PackageUpdate.byTitle(params['builds']).status == 'testing'

    def test_push_EPEL_before_tested(self):
        """
        Try pushing an epel package to stable after 13 days in testing, which
        will fail, and then try after 14 days.
        """
        session = login()
        rel = Release(name='EL5', long_name='Fedora EPEL 5',
                      id_prefix='FEDORA-EPEL', dist_tag='dist-5E-epel')
        params = {
                'builds'  : 'TurboGears-2.0.9-1.el5',
                'release' : 'Fedora EPEL 5',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foo',
                'autokarma': True,
                'stable_karma' : 1,
                'request': 'stable',
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing', update.request

        update.comment('This update has been pushed to testing', author='bodhi')
        update.comments[-1].timestamp -= timedelta(days=13)

        assert update.days_in_testing == 13

        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing', update.request

        update.comments[-2].timestamp -= timedelta(days=1)
        assert update.days_in_testing == 14, update.days_in_testing

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        log = testutil.get_log()
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable', log

    def test_replace_build_with_newer(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.8-1.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'security',
                'bugs'    : '',
                'notes'   : 'foobar',
                'request' : 'Stable',
                'autokarma' : True,
                'stable_karma' : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)

        # Add another build, for a different release
        params = {
            'builds'  : 'TurboGears-1.0.8-1.fc7.1',
            'release' : 'Fedora 7',
            'type_'   : 'bugfix',
            'cves'    : '',
            'bugs'    : '',
            'notes'   : 'foo',
            'edited'  : 'TurboGears-1.0.8-1.fc7',
        }

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()

        up = PackageUpdate.byTitle('TurboGears-1.0.8-1.fc7.1')
        assert up.comments[-1].text == 'guest has edited this update. New build(s): TurboGears-1.0.8-1.fc7.1. Removed build(s): TurboGears-1.0.8-1.fc7.'
        assert len(up.builds) == 1, logs
        try:
            PackageBuild.byNvr('TurboGears-1.0.8-1.fc7')
            assert False, "Removed build not deleted from database!"
        except SQLObjectNotFound:
            pass

    def test_push_EPEL_critpath_before_tested(self):
        """
        Try pushing an epel package to stable after 13 days in testing, which
        will fail, and then try after 14 days.
        """
        session = login()
        rel = Release(name='EL5', long_name='Fedora EPEL 5',
                      id_prefix='FEDORA-EPEL', dist_tag='dist-5E-epel')
        params = {
                'builds'  : 'kernel-2.6.31-1.el5',
                'release' : 'Fedora EPEL 5',
                'type_'   : 'bugfix',
                'bugs'    : '',
                'notes'   : 'foo',
                'autokarma': True,
                'stable_karma' : 1,
                'request': 'stable',
                'unstable_karma' : -1,
        }
        self.save_update(params, session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing', update.request

        update.comment('This update has been pushed to testing', author='bodhi')
        update.comments[-1].timestamp -= timedelta(days=13)

        assert update.days_in_testing == 13

        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'testing', update.request

        update.comments[-3].timestamp -= timedelta(days=1)
        assert update.days_in_testing == 14, update.days_in_testing

        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        testutil.create_request('/updates/request/stable/%s' % params['builds'],
                               method='POST', headers=session)
        log = testutil.get_log()
        update = PackageUpdate.byTitle(params['builds'])
        assert update.request == 'stable', log

    def test_comment_by_updateid(self):
        """ Ensure we can comment on updates using the updateid """
        session = login()
        create_release()
        params = {
                'builds'         : 'TurboGears-1.0.8-1.fc7',
                'type_'          : 'bugfix',
                'bugs'           : '',
                'notes'          : 'foobar',
                'request'        : 'Stable',
                'suggest_reboot' : True,
                'autokarma'      : True,
                'stable_karma'   : 5,
                'unstable_karma' : -5
        }
        testutil.capture_log(['bodhi.controller', 'bodhi.util'])
        self.save_update(params, session)
        log = testutil.get_log()
        up = PackageUpdate.byTitle(params['builds'])
        up.assign_id()
        assert up.updateid
        testutil.create_request('/updates/comment/foobar/%s' % up.updateid,
                                method='POST', headers=session)
        update = PackageUpdate.byTitle(params['builds'])
        assert update.comments[-1].text == 'foobar', update.comments

    def test_mandatory_notes(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '1234',
                'notes'   : '',
                'autokarma' : True
        }
        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()
        assert 'Error: You must supply details for this update' in logs
        
    def test_placeholder_notes(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'    : 'enhancement',
                'bugs'    : '1234',
                'notes'   : 'Here is where you give an explanation of your update.',
                'autokarma' : True
        }
        testutil.capture_log(['bodhi.controllers', 'bodhi.util', 'bodhi.model'])
        self.save_update(params, session)
        logs = testutil.get_log()
        assert 'Error: You must supply details for this update' in logs

    def test_new_updateid_url(self):
        session = login()
        create_release()
        params = {
                'builds'  : 'TurboGears-1.0.2.2-2.fc7',
                'release' : 'Fedora 7',
                'type_'   : 'enhancement',
                'bugs'    : '1234',
                'notes'   : 'notes go here',
        }
        self.save_update(params, session)
        up = PackageUpdate.byTitle(params['builds'])
        up.assign_id()
        testutil.create_request('/updates/' + up.updateid)
        assert 'notes go here' in cherrypy.response.body[0]
        testutil.create_request('/updates/%s/%s' % (up.updateid, up.title))
        assert 'notes go here' in cherrypy.response.body[0]

    def test_sort_updates(self):
        session = login()
        create_release()
        updates = []
        for rev in range(1, 10)[::-1]:
            params = {
                    'builds'         : 'TurboGears-1.0.8-%d.fc7' % rev,
                    'release'        : 'Fedora 7',
                    'type_'          : 'bugfix',
                    'bugs'           : '',
                    'notes'          : 'foobar',
                    'request'        : 'testing',
                    'suggest_reboot' : True,
                    'autokarma'      : True,
                    'stable_karma'   : 5,
                    'unstable_karma' : -5
            }
            self.save_update(params, session)
            up = PackageUpdate.byTitle(params['builds'])
            updates.append(up)
        params = {
                'builds'         : 'python-3.0-10.fc7',
                'release'        : 'Fedora 7',
                'type_'          : 'bugfix',
                'bugs'           : '',
                'notes'          : 'foobar',
                'request'        : 'testing',
                'suggest_reboot' : True,
                'autokarma'      : True,
                'stable_karma'   : 5,
                'unstable_karma' : -5
        }
        self.save_update(params, session)
        up = PackageUpdate.byTitle(params['builds'])
        updates.append(up)

        n, v, r = get_nvr(updates[0].builds[0].nvr)
        assert r == '9.fc7', r
        sorted_updates = sort_updates(updates)
        n, v, r = get_nvr(sorted_updates[0].builds[0].nvr)
        assert r == '1.fc7', r
        n, v, r = get_nvr(sorted_updates[-1].builds[0].nvr)
        assert r == '10.fc7', r
        n, v, r = get_nvr(sorted_updates[-2].builds[0].nvr)
        assert r == '9.fc7', r
        assert len(sorted_updates) == 10, len(sorted_updates)
