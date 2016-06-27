# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import copy
import textwrap
import time
import mock

from mock import ANY
from nose.tools import eq_
from datetime import datetime, timedelta
from webtest import TestApp

import bodhi.tests.functional.base

from bodhi import main
from bodhi.config import config
from bodhi.models import (
    Build,
    Group,
    Package,
    Update,
    User,
    UpdateStatus,
    UpdateRequest,
    Release,
    ReleaseState,
    BuildrootOverride,
    UpdateStatus,
    UpdateType,
)

YEAR = time.localtime().tm_year

mock_valid_requirements = {
    'target': 'bodhi.validators._get_valid_requirements',
    'return_value': ['rpmlint', 'upgradepath'],
}

mock_uuid4_version1 = {
    'target': 'uuid.uuid4',
    'return_value': 'this is a consistent string',
}
mock_uuid4_version2 = {
    'target': 'uuid.uuid4',
    'return_value': 'this is another consistent string',
}

mock_taskotron_results = {
    'target': 'bodhi.util.taskotron_results',
    'return_value': [{
        "outcome": "PASSED",
        "result_data": {},
        "testcase": { "name": "rpmlint", }
    }],
}

mock_failed_taskotron_results = {
    'target': 'bodhi.util.taskotron_results',
    'return_value': [{
        "outcome": "FAILED",
        "result_data": {},
        "testcase": { "name": "rpmlint", }
    }],
}

mock_absent_taskotron_results = {
    'target': 'bodhi.util.taskotron_results',
    'return_value': [],
}


class TestUpdatesService(bodhi.tests.functional.base.BaseWSGICase):

    def test_home_html(self):
        resp = self.app.get('/', headers={'Accept': 'text/html'})
        self.assertIn('Fedora Updates System', resp)
        self.assertIn('&copy;', resp)

    @mock.patch(**mock_valid_requirements)
    def test_invalid_build_name(self, *args):
        res = self.app.post_json('/updates/', self.get_update(u'bodhi-2.0-1.fc17,invalidbuild-1.0'),
                                 status=400)
        assert 'Build not in name-version-release format' in res, res

    @mock.patch(**mock_valid_requirements)
    def test_empty_build_name(self, *args):
        res = self.app.post_json('/updates/', self.get_update([u'']), status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'builds.0')
        self.assertEquals(res.json_body['errors'][0]['description'], 'Required')

    @mock.patch(**mock_valid_requirements)
    def test_fail_on_edit_with_empty_build_list(self, *args):
        update = self.get_update()
        update['edited'] = update['builds']  # the update title..
        update['builds'] = []
        res = self.app.post_json('/updates/', update, status=400)
        self.assertEquals(len(res.json_body['errors']), 2)
        self.assertEquals(res.json_body['errors'][0]['name'], 'builds')
        self.assertEquals(
            res.json_body['errors'][0]['description'],
            'You may not specify an empty list of builds.')
        self.assertEquals(res.json_body['errors'][1]['name'], 'builds')
        self.assertEquals(
            res.json_body['errors'][1]['description'],
            'ACL validation mechanism was unable to determine ACLs.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_unicode_description(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['notes'] = u'This is wünderfül'
        r = self.app.post_json('/updates/', update)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-2.fc17')
        self.assertEquals(up['notes'], u'This is wünderfül')
        self.assertIsNotNone(up['date_submitted'])
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)


    # FIXME: make it easy to tweak the tag of an update in our buildsys during unit tests
    #def test_invalid_tag(self):
    #    map(self.db.delete, self.db.query(Update).all())
    #    map(self.db.delete, self.db.query(Build).all())
    #    num = self.db.query(Update).count()
    #    assert num == 0, num
    #    res = self.app.post_json('/updates/', self.get_update(u'bodhi-1.0-1.fc17'),
    #                             status=400)
    #    assert 'Invalid tag' in res, res

    @mock.patch(**mock_valid_requirements)
    def test_duplicate_build(self, *args):
        res = self.app.post_json('/updates/',
            self.get_update([u'bodhi-2.0-2.fc17', u'bodhi-2.0-2.fc17']),
            status=400)
        assert 'Duplicate builds' in res, res

    @mock.patch(**mock_valid_requirements)
    def test_multiple_builds_of_same_package(self, *args):
        res = self.app.post_json('/updates/', self.get_update([u'bodhi-2.0-2.fc17',
                                                               u'bodhi-2.0-3.fc17']),
                                 status=400)
        assert 'Multiple bodhi builds specified' in res, res

    @mock.patch(**mock_valid_requirements)
    def test_invalid_autokarma(self, *args):
        res = self.app.post_json('/updates/', self.get_update(stable_karma=-1),
                                 status=400)
        assert '-1 is less than minimum value 1' in res, res
        res = self.app.post_json('/updates/', self.get_update(unstable_karma=1),
                                 status=400)
        assert '1 is greater than maximum value -1' in res, res

    @mock.patch(**mock_valid_requirements)
    def test_duplicate_update(self, *args):
        res = self.app.post_json('/updates/', self.get_update(u'bodhi-2.0-1.fc17'),
                                 status=400)
        assert 'Update for bodhi-2.0-1.fc17 already exists' in res, res

    @mock.patch(**mock_valid_requirements)
    def test_invalid_requirements(self, *args):
        update = self.get_update()
        update['requirements'] = 'rpmlint silly-dilly'
        res = self.app.post_json('/updates/', update, status=400)
        assert 'Invalid requirement' in res, res

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_no_privs(self, publish, *args):
        user = User(name=u'bodhi')
        self.db.add(user)
        self.db.flush()
        app = TestApp(main({}, testing=u'bodhi', session=self.db, **self.app_settings))
        res = app.post_json('/updates/', self.get_update(u'bodhi-2.1-1.fc17'),
                            status=400)
        assert 'bodhi does not have commit access to bodhi' in res, res
        self.assertEquals(publish.call_args_list, [])

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_provenpackager_privs(self, publish, *args):
        "Ensure provenpackagers can push updates for any package"
        user = User(name=u'bodhi')
        self.db.add(user)
        self.db.flush()
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)

        app = TestApp(main({}, testing=u'bodhi', session=self.db, **self.app_settings))
        update = self.get_update(u'bodhi-2.1-1.fc17')
        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        res = app.post_json('/updates/', update)
        assert 'bodhi does not have commit access to bodhi' not in res, res
        build = self.db.query(Build).filter_by(nvr=u'bodhi-2.1-1.fc17').one()
        assert build.update is not None
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_provenpackager_edit_anything(self, publish, *args):
        "Ensure provenpackagers can edit updates for any package"
        nvr = u'bodhi-2.1-1.fc17'

        user = User(name=u'lloyd')
        self.db.add(user)
        self.db.add(User(name=u'ralph'))  # Add a non proventester
        self.db.flush()
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)

        app = TestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))
        up_data = self.get_update(nvr)
        up_data['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        res = app.post_json('/updates/', up_data)
        assert 'does not have commit access to bodhi' not in res, res
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        app = TestApp(main({}, testing=u'lloyd', session=self.db, **self.app_settings))
        update = self.get_update(nvr)
        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        update['notes'] = u'testing!!!'
        update['edited'] = nvr
        res = app.post_json('/updates/', update)
        assert 'bodhi does not have commit access to bodhi' not in res, res
        build = self.db.query(Build).filter_by(nvr=nvr).one()
        assert build.update is not None
        self.assertEquals(build.update.notes, u'testing!!!')
        #publish.assert_called_once_with(
        #    topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_provenpackager_request_privs(self, publish, *args):
        "Ensure provenpackagers can change the request for any update"
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        self.db.add(user)
        self.db.add(User(name=u'ralph'))  # Add a non proventester
        self.db.add(User(name=u'someuser'))  # An unrelated user with no privs
        self.db.flush()
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)

        app = TestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))
        up_data = self.get_update(nvr)
        up_data['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        res = app.post_json('/updates/', up_data)
        assert 'does not have commit access to bodhi' not in res, res
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(Build).filter_by(nvr=nvr).one()
        eq_(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a non-provenpackager
        app = TestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))
        post_data = dict(update=nvr, request='stable',
                         csrf_token=app.get('/csrf').json_body['csrf_token'])
        res = app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure we can't push it until it meets the requirements
        eq_(res.json_body['status'], 'error')
        eq_(res.json_body['errors'][0]['description'], config.get('not_yet_tested_msg'))

        update = self.db.query(Update).filter_by(title=nvr).one()
        eq_(update.stable_karma, 3)
        eq_(update.locked, False)
        eq_(update.request, UpdateRequest.testing)

        # Pretend it was pushed to testing
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.flush()

        eq_(update.karma, 0)
        update.comment(self.db, u"foo", 1, u'foo')
        update = self.db.query(Update).filter_by(title=nvr).one()
        eq_(update.karma, 1)
        eq_(update.request, None)
        update.comment(self.db, u"foo", 1, u'bar')
        update = self.db.query(Update).filter_by(title=nvr).one()
        eq_(update.karma, 2)
        eq_(update.request, None)
        update.comment(self.db, u"foo", 1, u'biz')
        update = self.db.query(Update).filter_by(title=nvr).one()
        eq_(update.karma, 3)
        eq_(update.request, UpdateRequest.stable)

        # Set it back to testing
        update.request = UpdateRequest.testing

        # Try and submit the update to stable as a proventester
        app = TestApp(main({}, testing=u'bob', session=self.db, **self.app_settings))
        res = app.post_json('/updates/%s/request' % str(nvr),
                            dict(update=nvr, request='stable',
                                csrf_token=app.get('/csrf').json_body['csrf_token']),
                            status=200)

        eq_(res.json_body['update']['request'], 'stable')

        app = TestApp(main({}, testing=u'bob', session=self.db, **self.app_settings))
        res = app.post_json('/updates/%s/request' % str(nvr),
                            dict(update=nvr, request='obsolete',
                                 csrf_token=app.get('/csrf').json_body['csrf_token']),
                            status=200)

        eq_(res.json_body['update']['request'], None)
        eq_(update.request, None)
        eq_(update.status, UpdateStatus.obsolete)

        # Test that bob has can_edit True, provenpackager
        app = TestApp(main({}, testing=u'bob', session=self.db, **self.app_settings))
        res = app.get('/updates/%s' % str(nvr), status=200)
        eq_(res.json_body['can_edit'], True)

        # Test that ralph has can_edit True, they submitted it.
        app = TestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))
        res = app.get('/updates/%s' % str(nvr), status=200)
        eq_(res.json_body['can_edit'], True)

        # Test that someuser has can_edit False, they are unrelated
        # This check *failed* with the old acls code.
        app = TestApp(main({}, testing=u'someuser', session=self.db, **self.app_settings))
        res = app.get('/updates/%s' % str(nvr), status=200)
        eq_(res.json_body['can_edit'], False)

        # Test that an anonymous user has can_edit False, obv.
        # This check *crashed* with the code on 2015-09-24.
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })

        app = TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/updates/%s' % str(nvr), status=200)
        eq_(res.json_body['can_edit'], False)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_old_bodhi1_redirect(self, publish, *args):
        # Create it
        title = 'bodhi-2.0.0-1.fc17'
        self.app.post_json('/updates/', self.get_update(title))
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        # Get it once with just the title
        url = '/updates/%s' % title
        res = self.app.get(url)
        update = res.json_body['update']

        # Now try the old bodhi1 url.  Redirect should take place.
        url = '/updates/%s/%s' % (update['alias'], update['title'])
        res = self.app.get(url, status=302)
        target = 'http://localhost/updates/%s' % update['alias']
        self.assertEquals(res.headers['Location'], target)

    @mock.patch(**mock_valid_requirements)
    def test_pkgdb_outage(self, *args):
        "Test the case where our call to the pkgdb throws an exception"
        settings = self.app_settings.copy()
        settings['acl_system'] = 'pkgdb'
        settings['pkgdb_url'] = 'invalidurl'
        app = TestApp(main({}, testing=u'guest', session=self.db, **settings))
        update = self.get_update(u'bodhi-2.0-2.fc17')
        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        res = app.post_json('/updates/', update, status=400)
        assert "Unable to access the Package Database" in res, res

    @mock.patch(**mock_valid_requirements)
    def test_invalid_acl_system(self, *args):
        settings = self.app_settings.copy()
        settings['acl_system'] = 'null'
        app = TestApp(main({}, testing=u'guest', session=self.db, **settings))
        res = app.post_json('/updates/', self.get_update(u'bodhi-2.0-2.fc17'),
                            status=400)
        assert "guest does not have commit access to bodhi" in res, res

    def test_404(self):
        self.app.get('/a', status=404)

    def test_get_single_update(self):
        res = self.app.get('/updates/bodhi-2.0-1.fc17')
        self.assertEquals(res.json_body['update']['title'], 'bodhi-2.0-1.fc17')
        self.assertIn('application/json', res.headers['Content-Type'])

    def test_get_single_update_jsonp(self):
        res = self.app.get('/updates/bodhi-2.0-1.fc17',
                           {'callback': 'callback'},
                           headers={'Accept': 'application/javascript'})
        self.assertIn('application/javascript', res.headers['Content-Type'])
        self.assertIn('callback', res)
        self.assertIn('bodhi-2.0-1.fc17', res)

    def test_get_single_update_rss(self):
        self.app.get('/updates/bodhi-2.0-1.fc17',
                     headers={'Accept': 'application/atom+xml'},
                     status=406)

    def test_get_single_update_html(self):
        id = 'bodhi-2.0-1.fc17'
        resp = self.app.get('/updates/%s' % id,
                            headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertIn('&copy;', resp)

    def test_list_updates(self):
        res = self.app.get('/updates/')
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        alias = u'FEDORA-%s-a3bbe1a8f2' % YEAR
        baseurl = 'http://0.0.0.0:6543'

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['submitter'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], alias)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(up['url'], '%s/updates/%s' % (baseurl, alias))

    def test_list_updates_jsonp(self):
        res = self.app.get('/updates/',
                           {'callback': 'callback'},
                           headers={'Accept': 'application/javascript'})
        self.assertIn('application/javascript', res.headers['Content-Type'])
        self.assertIn('callback', res)
        self.assertIn('bodhi-2.0-1.fc17', res)

    def test_list_updates_rss(self):
        res = self.app.get('/rss/updates/',
                           headers={'Accept': 'application/atom+xml'})
        self.assertIn('application/rss+xml', res.headers['Content-Type'])
        self.assertIn('bodhi-2.0-1.fc17', res)

    def test_list_updates_html(self):
        res = self.app.get('/updates/',
                           headers={'Accept': 'text/html'})
        self.assertIn('text/html', res.headers['Content-Type'])
        self.assertIn('bodhi-2.0-1.fc17', res)
        self.assertIn('&copy;', res)

    def test_search_updates(self):
        res = self.app.get('/updates/', {'like': 'odh'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

        res = self.app.get('/updates/', {'like': 'wat'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_pagination(self):

        # First, stuff a second update in there
        self.test_new_update()

        # Then, test pagination
        res = self.app.get('/updates/',
                           {"rows_per_page": 1})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        update1 = body['updates'][0]

        res = self.app.get('/updates/',
                           {"rows_per_page": 1, "page": 2})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        update2 = body['updates'][0]

        self.assertNotEquals(update1, update2)

    def test_list_updates_by_approved_since(self):
        now = datetime.utcnow()

        # Try with no approved updates first
        res = self.app.get('/updates/',
                           {"approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        self.db.query(Update).first().date_approved = now
        self.db.flush()

        # And try again
        res = self.app.get('/updates/',
                           {"approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

        # https://github.com/fedora-infra/bodhi/issues/270
        self.assertEquals(len(up['test_cases']), 1)
        self.assertEquals(up['test_cases'][0]['name'], u'Wat')

    def test_list_updates_by_invalid_approved_since(self):
        res = self.app.get('/updates/', {"approved_since": "forever"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'approved_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_approved_before(self):
        # Approve an update
        now = datetime.utcnow()
        self.db.query(Update).first().date_approved = now
        self.db.flush()

        # First check we get no result for an old date
        res = self.app.get('/updates/',
                           {"approved_before": "1984-11-01"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now check we get the update if we use tomorrow
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        res = self.app.get('/updates/', {"approved_before": tomorrow})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_approved_before(self):
        res = self.app.get('/updates/', {"approved_before": "forever"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'approved_before')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_bugs(self):
        res = self.app.get('/updates/', {"bugs": '12345'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_bug(self):
        res = self.app.get('/updates/', {"bugs": "cockroaches"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'bugs')
        self.assertEquals(res.json_body['errors'][0]['description'],
                "Invalid bug ID specified: [u'cockroaches']")

    def test_list_updates_by_unexisting_bug(self):
        res = self.app.get('/updates/', {"bugs": "19850110"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_critpath(self):
        res = self.app.get('/updates/', {"critpath": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_invalid_critpath(self):
        res = self.app.get('/updates/', {"critpath": "lalala"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'critpath')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"lalala" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_cves(self):
        res = self.app.get("/updates/", {"cves": "CVE-1985-0110"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        #self.assertEquals(up['cves'][0]['cve_id'], "CVE-1985-0110")

    def test_list_updates_by_unexisting_cve(self):
        res = self.app.get('/updates/', {"cves": "CVE-2013-1015"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_invalid_cve(self):
        res = self.app.get('/updates/', {"cves": "WTF-ZOMG-BBQ"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'cves.0')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"WTF-ZOMG-BBQ" is not a valid CVE id')

    def test_list_updates_by_date_submitted_invalid_date(self):
        """test filtering by submitted date with an invalid date"""
        res = self.app.get('/updates/', {"submitted_since": "11-01-1984"},
            status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(body['errors'][0]['name'], 'submitted_since')
        self.assertEquals(body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_date_submitted_future_date(self):
        """test filtering by submitted date with future date"""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        res = self.app.get('/updates/', {"submitted_since": tomorrow})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_date_submitted_valid(self):
        """test filtering by submitted date with valid data"""
        res = self.app.get('/updates/', {"submitted_since": "1984-11-01"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_date_submitted_before_invalid_date(self):
        """test filtering by submitted before date with an invalid date"""
        res = self.app.get('/updates/', {"submitted_before": "11-01-1984"},
            status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(body['errors'][0]['name'], 'submitted_before')
        self.assertEquals(body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_date_submitted_before_old_date(self):
        """test filtering by submitted before date with old date"""
        res = self.app.get('/updates/', {"submitted_before": "1975-01-01"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_date_submitted_before_valid(self):
        """test filtering by submitted before date with valid date"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        res = self.app.get('/updates/', {"submitted_before": today})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_locked(self):
        res = self.app.get('/updates/', {"locked": "true"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_invalid_locked(self):
        res = self.app.get('/updates/', {"locked": "maybe"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'locked')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"maybe" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_modified_since(self):
        now = datetime.utcnow()

        # Try with no modified updates first
        res = self.app.get('/updates/',
                           {"modified_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        self.db.query(Update).first().date_modified = now
        self.db.flush()

        # And try again
        res = self.app.get('/updates/',
                           {"modified_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_modified_since(self):
        res = self.app.get('/updates/', {"modified_since": "the dawn of time"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'modified_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_modified_before(self):
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        # Try with no modified updates first
        res = self.app.get('/updates/',
                           {"modified_before": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        self.db.query(Update).first().date_modified = now
        self.db.flush()

        # And try again
        res = self.app.get('/updates/',
                           {"modified_before": tomorrow})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_modified_before(self):
        res = self.app.get('/updates/', {"modified_before": "the dawn of time"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'modified_before')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_package(self):
        res = self.app.get('/updates/', {"packages": "bodhi"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_builds(self):
        res = self.app.get('/updates/', {"builds": "bodhi-3.0-1.fc17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        res = self.app.get('/updates/', {"builds": "bodhi-2.0-1.fc17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_package(self):
        res = self.app.get('/updates/', {"packages": "flash-player"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_pushed(self):
        res = self.app.get('/updates/', {"pushed": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(up['pushed'], False)

    def test_list_updates_by_invalid_pushed(self):
        res = self.app.get('/updates/', {"pushed": "who knows?"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'pushed')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"who knows?" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_pushed_since(self):
        now = datetime.utcnow()

        # Try with no pushed updates first
        res = self.app.get('/updates/',
                           {"pushed_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        self.db.query(Update).first().date_pushed = now
        self.db.flush()

        # And try again
        res = self.app.get('/updates/',
                           {"pushed_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_pushed_since(self):
        res = self.app.get('/updates/', {"pushed_since": "a while ago"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'pushed_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_pushed_before(self):
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        # Try with no pushed updates first
        res = self.app.get('/updates/',
                           {"pushed_before": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        self.db.query(Update).first().date_pushed = now
        self.db.flush()

        # And try again
        res = self.app.get('/updates/',
                           {"pushed_before": tomorrow})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_pushed_before(self):
        res = self.app.get('/updates/', {"pushed_before": "a while ago"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'pushed_before')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_release_name(self):
        res = self.app.get('/updates/', {"releases": "F17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_release_version(self):
        res = self.app.get('/updates/', {"releases": "17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_release(self):
        res = self.app.get('/updates/', {"releases": "WinXP"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'releases')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid releases specified: WinXP')

    def test_list_updates_by_request(self):
        res = self.app.get('/updates/', {'request': "testing"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_request(self):
        res = self.app.get('/updates/', {"request": "impossible"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'request')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"impossible" is not one of unpush, testing, revoke,'
                          ' obsolete, stable')

    def test_list_updates_by_severity(self):
        res = self.app.get('/updates/', {"severity": "unspecified"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_severity(self):
        res = self.app.get('/updates/', {"severity": "schoolmaster"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'severity')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"schoolmaster" is not one of high, urgent, medium, low, unspecified')

    def test_list_updates_by_status(self):
        res = self.app.get('/updates/', {"status": "pending"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_status(self):
        res = self.app.get('/updates/', {"status": "single"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'status')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"single" is not one of testing, processing, obsolete, stable, unpushed, pending')

    def test_list_updates_by_suggest(self):
        res = self.app.get('/updates/', {"suggest": "unspecified"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_suggest(self):
        res = self.app.get('/updates/', {"suggest": "no idea"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'suggest')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"no idea" is not one of logout, reboot, unspecified')

    def test_list_updates_by_type(self):
        res = self.app.get('/updates/', {"type": "bugfix"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_type(self):
        res = self.app.get('/updates/', {"type": "not_my"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'type')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"not_my" is not one of newpackage, bugfix, security, enhancement')

    def test_list_updates_by_username(self):
        res = self.app.get('/updates/', {"user": "guest"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], True)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_unexisting_username(self):
        res = self.app.get('/updates/', {"user": "santa"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'user')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid user specified: santa")

    def test_put_json_update(self):
        self.app.put_json('/updates/', self.get_update(), status=405)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_post_json_update(self, publish, *args):
        self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-1.fc17'))
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_new_update(self, publish, *args):
        r = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'))
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-2.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'this is a test update')
        self.assertIsNotNone(up['date_submitted'])
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-033713b73b' % YEAR)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['requirements'], 'rpmlint')
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_new_update_with_multiple_bugs(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = ['1234', '5678']
        r = self.app.post_json('/updates/', update)
        up = r.json_body
        self.assertEquals(len(up['bugs']), 2)
        self.assertEquals(up['bugs'][0]['bug_id'], 1234)
        self.assertEquals(up['bugs'][1]['bug_id'], 5678)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_new_update_with_multiple_bugs_as_str(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = '1234, 5678'
        r = self.app.post_json('/updates/', update)
        up = r.json_body
        self.assertEquals(len(up['bugs']), 2)
        self.assertEquals(up['bugs'][0]['bug_id'], 1234)
        self.assertEquals(up['bugs'][1]['bug_id'], 5678)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_new_update_with_invalid_bugs_as_str(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = '1234, blargh'
        r = self.app.post_json('/updates/', update, status=400)
        up = r.json_body
        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'],
                          "Invalid bug ID specified: [u'1234', u'blargh']")

    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_update(self, publish, *args):
        args = self.get_update('bodhi-2.0.0-2.fc17')
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        args['requirements'] = 'upgradepath'
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'this is a test update')
        self.assertIsNotNone(up['date_submitted'])
        self.assertIsNotNone(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-033713b73b' % YEAR)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['requirements'], 'upgradepath')
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17
        """).strip()
        self.assertMultiLineEqual(up['comments'][-1]['text'], comment)
        self.assertEquals(len(up['builds']), 1)
        self.assertEquals(up['builds'][0]['nvr'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(self.db.query(Build).filter_by(nvr=u'bodhi-2.0.0-2.fc17').first(), None)
        self.assertEquals(len(publish.call_args_list), 2)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_testing_update_with_new_builds(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing
        upd = Update.get(nvr, self.db)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.flush()

        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        #assert False, '\n'.join([c['text'] for c in up['comments']])
        self.assertEquals(up['comments'][-1]['text'],
                          u'This update has been submitted for testing by guest. ')
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17
        """).strip()
        self.assertMultiLineEqual(up['comments'][-2]['text'], comment)
        self.assertEquals(up['comments'][-3]['text'],
                          u'This update has been submitted for testing by guest. ')
        self.assertEquals(len(up['builds']), 1)
        self.assertEquals(up['builds'][0]['nvr'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(self.db.query(Build).filter_by(nvr=u'bodhi-2.0.0-2.fc17').first(), None)
        self.assertEquals(len(publish.call_args_list), 3)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_testing_update_with_new_builds_with_stable_request(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing
        upd = Update.get(nvr, self.db)
        upd.status = UpdateStatus.testing
        upd.request = UpdateRequest.stable
        self.db.flush()

        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['comments'][-1]['text'],
                          u'This update has been submitted for testing by guest. ')
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17
        """).strip()
        self.assertMultiLineEqual(up['comments'][-2]['text'], comment)
        self.assertEquals(up['comments'][-3]['text'],
                          u'This update has been submitted for testing by guest. ')
        self.assertEquals(len(up['builds']), 1)
        self.assertEquals(up['builds'][0]['nvr'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(self.db.query(Build).filter_by(nvr=u'bodhi-2.0.0-2.fc17').first(), None)
        self.assertEquals(len(publish.call_args_list), 3)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_update_with_different_release(self, publish, *args):
        """Test editing an update for one release with builds from another."""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update('bodhi-2.0.0-2.fc17')
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Add another release and package
        Release._tag_cache = None
        release = Release(
            name=u'F18', long_name=u'Fedora 18',
            id_prefix=u'FEDORA', version=u'18',
            dist_tag=u'f18', stable_tag=u'f18-updates',
            testing_tag=u'f18-updates-testing',
            candidate_tag=u'f18-updates-candidate',
            pending_testing_tag=u'f18-updates-testing-pending',
            pending_stable_tag=u'f18-updates-pending',
            override_tag=u'f18-override',
            branch=u'f18')
        self.db.add(release)
        pkg = Package(name=u'nethack')
        self.db.add(pkg)

        args = self.get_update('bodhi-2.0.0-2.fc17,nethack-4.0.0-1.fc18')
        args['edited'] = nvr
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body

        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'],
                          'Cannot add a F18 build to an F17 update')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_cascade_package_requirements_to_update(self, publish, *args):

        package = self.db.query(Package).filter_by(name=u'bodhi').one()
        package.requirements = u'upgradepath rpmlint'
        self.db.flush()

        args = self.get_update(u'bodhi-2.0.0-3.fc17')
        # Don't specify any requirements so that they cascade from the package
        del args['requirements']
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(up['requirements'], 'upgradepath rpmlint')
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_stable_update(self, publish, *args):
        """Make sure we can't edit stable updates"""
        self.assertEquals(publish.call_args_list, [])

        # First, create a testing update
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args, status=200)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        # Then, switch it to stable behind the scenes
        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.stable

        # Then, try to edit it through the api again
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body
        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'], "Cannot edit stable updates")
        self.assertEquals(len(publish.call_args_list), 1)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_locked_update(self, publish, *args):
        """Make sure some changes are prevented"""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args, status=200)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = True
        up.status = UpdateStatus.testing
        up.request = None
        up_id = up.id

        build = self.db.query(Build).filter_by(nvr=nvr).one()

        # Changing the notes should work
        args['edited'] = args['builds']
        args['notes'] = 'Some new notes'
        up = self.app.post_json('/updates/', args, status=200).json_body
        self.assertEquals(up['notes'], 'Some new notes')

        # Changing the builds should fail
        args['notes'] = 'And yet some other notes'
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args, status=400).json_body
        self.assertEquals(r['status'], 'error')
        self.assertIn('errors', r)
        self.assertIn({u'description': u"Can't add builds to a locked update",
                       u'location': u'body', u'name': u'builds'},
                      r['errors'])
        up = self.db.query(Update).get(up_id)
        self.assertEquals(up.notes, 'Some new notes')
        self.assertEquals(up.builds, [build])

        # Changing the request should fail
        args['notes'] = 'Still new notes'
        args['builds'] = args['edited']
        args['request'] = 'stable'
        r = self.app.post_json('/updates/', args, status=400).json_body
        self.assertEquals(r['status'], 'error')
        self.assertIn('errors', r)
        self.assertIn({u'description': u"Can't change the request on a "
                                        "locked update",
                       u'location': u'body', u'name': u'builds'},
                      r['errors'])
        up = self.db.query(Update).get(up_id)
        self.assertEquals(up.notes, 'Some new notes')
        self.assertEquals(up.builds, [build])
        self.assertEquals(up.request, None)

        # At the end of the day, two fedmsg messages should have gone out.
        self.assertEquals(len(publish.call_args_list), 2)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_push_untested_critpath_to_release(self, publish, *args):
        """
        Ensure that we cannot push an untested critpath update directly to
        stable.
        """
        args = self.get_update('kernel-3.11.5-300.fc17')
        args['request'] = 'stable'
        up = self.app.post_json('/updates/', args).json_body
        self.assertTrue(up['critpath'])
        self.assertEquals(up['request'], 'testing')
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_obsoletion(self, publish, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with mock.patch(**mock_uuid4_version1):
            self.app.post_json('/updates/', args)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)
        publish.call_args_list = []

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.testing
        up.request = None

        args = self.get_update('bodhi-2.0.0-3.fc17')
        with mock.patch(**mock_uuid4_version2):
            r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')

        # Since we're obsoleting something owned by someone else.
        self.assertEquals(r['caveats'][0]['description'],
                          'This update has obsoleted bodhi-2.0.0-2.fc17, '
                          'and has inherited its bugs and notes.')

        # Check for the comment multiple ways
        # Note that caveats above don't support markdown, but comments do.
        self.assertEquals(r['comments'][-1]['text'],
                          u'This update has obsoleted [bodhi-2.0.0-2.fc17]'
                          '(http://0.0.0.0:6543/updates/FEDORA-2016-033713b73b), '
                          'and has inherited its bugs and notes.')
        publish.assert_called_with(
            topic='update.request.testing', msg=mock.ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.obsolete)
        self.assertEquals(up.comments[-1].text,
                          u'This update has been obsoleted by '
                          '[bodhi-2.0.0-3.fc17](http://0.0.0.0:6543/'
                          'updates/FEDORA-2016-53345602d5).')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_obsoletion_locked_with_open_request(self, publish, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = True
        self.db.flush()

        args = self.get_update('bodhi-2.0.0-3.fc17')
        r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.testing)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_obsoletion_unlocked_with_open_request(self, publish, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args)

        args = self.get_update('bodhi-2.0.0-3.fc17')
        r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.obsolete)
        self.assertEquals(up.request, None)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_obsoletion_unlocked_with_open_stable_request(self, publish, *args):
        """ Ensure that we don't obsolete updates that have a stable request """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = UpdateRequest.stable
        self.db.flush()

        args = self.get_update('bodhi-2.0.0-3.fc17')
        r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.stable)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_push_to_stable_for_obsolete_update(self, publish, *args):
        """
        Obsolete update should not be submitted to testing
        Test Push to Stable option for obsolete update
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with mock.patch(**mock_uuid4_version1):
            self.app.post_json('/updates/', args)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)
        publish.call_args_list = []

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.testing
        up.request = None

        new_nvr = 'bodhi-2.0.0-3.fc17'
        args = self.get_update(new_nvr)
        with mock.patch(**mock_uuid4_version2):
            r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')
        publish.assert_called_with(
            topic='update.request.testing', msg=mock.ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.obsolete)
        self.assertEquals(up.comments[-1].text,
                          u'This update has been obsoleted by '
                          '[bodhi-2.0.0-3.fc17](http://0.0.0.0:6543/'
                          'updates/FEDORA-2016-53345602d5).')

        # Check Push to Stable button for obsolete update
        id = 'bodhi-2.0.0-2.fc17'
        resp = self.app.get('/updates/%s' % id,
                        headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertNotIn('Push to Stable', resp)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_invalid_request(self, *args):
        """Test submitting an invalid request"""
        args = self.get_update()
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'foo','csrf_token': self.get_csrf_token()}, status=400)
        resp = resp.json_body
        eq_(resp['status'], 'error')
        eq_(resp['errors'][0]['description'], u'"foo" is not one of unpush, testing, revoke, obsolete, stable')

        # Now try with None
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': None, 'csrf_token': self.get_csrf_token()}, status=400)
        resp = resp.json_body
        eq_(resp['status'], 'error')
        eq_(resp['errors'][0]['name'], 'request')
        eq_(resp['errors'][0]['description'], 'Required')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_testing_request(self, publish, *args):
        """Test submitting a valid testing request"""
        Update.get(u'bodhi-2.0-1.fc17', self.db).locked = False

        args = self.get_update()
        args['request'] = None
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'testing', 'csrf_token': self.get_csrf_token()})
        eq_(resp.json['update']['request'], 'testing')
        self.assertEquals(publish.call_args_list, [])

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_revoke_action_for_stable_request(self, publish, *args):
        """
        Test revoke action for stable request on testing update
        and check status after revoking the request
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = UpdateRequest.stable
        self.db.flush()

        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'revoke', 'csrf_token': self.get_csrf_token()})
        eq_(resp.json['update']['request'], None)
        eq_(resp.json['update']['status'], 'testing')
        publish.assert_called_with(
                topic='update.request.revoke', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_revoke_action_for_testing_request(self, publish, *args):
        """
        Test revoke action for testing request on pending update
        and check status after revoking the request
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        self.db.flush()

        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'revoke', 'csrf_token': self.get_csrf_token()})
        eq_(resp.json['update']['request'], None)
        eq_(resp.json['update']['status'], 'unpushed')
        publish.assert_called_with(
                topic='update.request.revoke', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_request_after_unpush(self, publish, *args):
        """Test request of this update after unpushing"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = UpdateRequest.stable
        self.db.flush()

        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'unpush', 'csrf_token': self.get_csrf_token()})
        eq_(resp.json['update']['request'], None)
        eq_(resp.json['update']['status'], 'unpushed')
        publish.assert_called_with(
                topic='update.request.unpush', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_invalid_stable_request(self, *args):
        """Test submitting a stable request for an update that has yet to meet the stable requirements"""
        Update.get(u'bodhi-2.0-1.fc17', self.db).locked = False

        args = self.get_update()
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        eq_(resp.json['status'], 'error')
        eq_(resp.json['errors'][0]['description'],
            config.get('not_yet_tested_msg'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_request_to_stable_based_on_stable_karma(self, *args):
        """
        Test request to stable before an update reaches stable karma
        and after it reaches stable karma when autokarma is disabled
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.flush()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        resp = self.app.post_json('/updates/', args)

        up = Update.get(nvr, self.db)
        up.status = UpdateStatus.testing
        up.request = None
        self.db.flush()

        # Checks failure for requesting to stable push before the update reaches stable karma
        up.comment(self.db, u'Not working', author=u'ralph', karma=0)
        up = Update.get(nvr, self.db)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertEquals(up.request, None)
        self.assertEquals(up.status, UpdateStatus.testing)

        # Checks Success for requesting to stable push after the update reaches stable karma
        up.comment(self.db, u'LGTM', author=u'ralph', karma=1)
        up = Update.get(nvr, self.db)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=200)
        self.assertEquals(up.request, UpdateRequest.stable)
        self.assertEquals(up.status, UpdateStatus.testing)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_stable_request_after_testing(self, publish, *args):
        """Test submitting a stable request to an update that has met the minimum amount of time in testing"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        self.db.flush()
        eq_(up.days_in_testing, 7)
        eq_(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()})
        eq_(resp.json['update']['request'], 'stable')
        publish.assert_called_with(
            topic='update.request.stable', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_request_to_archived_release(self, publish, *args):
        """Test submitting a stable request to an update for an archived/EOL release.
        https://github.com/fedora-infra/bodhi/issues/725
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.pending
        up.request = None
        up.release.state = ReleaseState.archived
        self.db.flush()
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'testing', 'csrf_token': self.get_csrf_token()},
            status=400)
        eq_(resp.json['status'], 'error')
        eq_(resp.json['errors'][0]['description'],
            "Can't change request for an archived release")

    @mock.patch(**mock_failed_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_stable_request_failed_taskotron_results(self, publish, *args):
        """Test submitting a stable request, but with bad taskotron results"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        self.db.flush()
        eq_(up.days_in_testing, 7)
        eq_(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertIn('errors', resp)
        self.assertIn('Required task', resp)

    @mock.patch(**mock_absent_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_stable_request_absent_taskotron_results(self, publish, *args):
        """Test submitting a stable request, but with absent task results"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        self.db.flush()
        eq_(up.days_in_testing, 7)
        eq_(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertIn('errors', resp)
        self.assertIn('No result found for', resp)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_stable_request_when_stable(self, publish, *args):
        """Test submitting a stable request to an update that already been
        pushed to stable"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.stable
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=14)
        up.comment(self.db, 'This update has been pushed to stable', author='bodhi')
        self.db.flush()
        eq_(up.days_in_testing, 14)
        eq_(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()})
        eq_(resp.json['update']['status'], 'stable')
        eq_(resp.json['update']['request'], None)
        try:
            publish.assert_called_with(
                topic='update.request.stable', msg=mock.ANY)
            assert False, "request.stable fedmsg shouldn't have fired"
        except AssertionError:
            pass

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_testing_request_when_testing(self, publish, *args):
        """Test submitting a testing request to an update that already been
        pushed to testing"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=14)
        self.db.flush()
        eq_(up.days_in_testing, 14)
        eq_(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'testing', 'csrf_token': self.get_csrf_token()})
        eq_(resp.json['update']['status'], 'testing')
        eq_(resp.json['update']['request'], None)
        try:
            publish.assert_called_with(
                topic='update.request.testing', msg=mock.ANY)
            assert False, "request.testing fedmsg shouldn't have fired"
        except AssertionError:
            pass

    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_existing_build(self, *args):
        """Test submitting a new update with a build already in the database"""
        package = Package.get('bodhi', self.db)
        self.db.add(Build(nvr=u'bodhi-2.0.0-3.fc17', package=package))
        self.db.flush()

        args = self.get_update(u'bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)

        eq_(resp.json['title'], 'bodhi-2.0.0-3.fc17')

    @mock.patch(**mock_valid_requirements)
    def test_update_with_older_build_in_testing_from_diff_user(self, r):
        """
        Test submitting an update for a package that has an older build within
        a multi-build update currently in testing submitted by a different
        maintainer.

        https://github.com/fedora-infra/bodhi/issues/78
        """
        title = u'bodhi-2.0-2.fc17 python-3.0-1.fc17'
        args = self.get_update(title)
        resp = self.app.post_json('/updates/', args)
        newuser = User(name=u'bob')
        self.db.add(newuser)
        up = self.db.query(Update).filter_by(title=title).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.user = newuser
        self.db.flush()

        newtitle = u'bodhi-2.0-3.fc17'
        args = self.get_update(newtitle)
        resp = self.app.post_json('/updates/', args)

        # Note that this does **not** obsolete the other update
        print resp.json_body['caveats']
        self.assertEquals(len(resp.json_body['caveats']), 1)
        self.assertEquals(resp.json_body['caveats'][0]['description'],
                          "Please be aware that there is another update in "
                          "flight owned by bob, containing "
                          "bodhi-2.0-2.fc17.  Are you coordinating with "
                          "them?")

        # Ensure the second update was created successfully
        self.db.query(Update).filter_by(title=newtitle).one()

    @mock.patch(**mock_valid_requirements)
    def test_updateid_alias(self, *args):
        res = self.app.post_json('/updates/', self.get_update(u'bodhi-2.0.0-3.fc17'))
        json = res.json_body
        self.assertEquals(json['alias'], json['updateid'])

    def test_list_updates_by_lowercase_release_name(self):
        res = self.app.get('/updates/', {"releases": "f17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

    def test_redirect_to_package(self):
        "When you visit /updates/package, redirect to /updates/?packages=..."
        res = self.app.get('/updates/bodhi', status=302)
        target = 'http://localhost/updates/?packages=bodhi'
        self.assertEquals(res.headers['Location'], target)

        # But be sure that we don't redirect if the package doesn't exist
        res = self.app.get('/updates/non-existant', status=404)

    def test_list_updates_by_alias_and_updateid(self):
        upd = self.db.query(Update).filter(Update.alias != None).first()
        res = self.app.get('/updates/', {"alias": upd.alias})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], upd.title)
        self.assertEquals(up['alias'], upd.alias)

        res = self.app.get('/updates/', {"updateid": upd.alias})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], upd.title)

        res = self.app.get('/updates/', {"updateid": 'BLARG'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_submitting_multi_release_updates(self, publish, *args):
        """ https://github.com/fedora-infra/bodhi/issues/219 """
        # Add another release and package
        Release._tag_cache = None
        release = Release(
            name=u'F18', long_name=u'Fedora 18',
            id_prefix=u'FEDORA', version=u'18',
            dist_tag=u'f18', stable_tag=u'f18-updates',
            testing_tag=u'f18-updates-testing',
            candidate_tag=u'f18-updates-candidate',
            pending_testing_tag=u'f18-updates-testing-pending',
            pending_stable_tag=u'f18-updates-pending',
            override_tag=u'f18-override',
            branch=u'f18')
        self.db.add(release)
        pkg = Package(name=u'nethack')
        self.db.add(pkg)

        # A multi-release submission!!!  This should create *two* updates
        args = self.get_update('bodhi-2.0.0-2.fc17,bodhi-2.0.0-2.fc18')
        r = self.app.post_json('/updates/', args)
        data = r.json_body

        self.assertIn('caveats', data)
        import pprint; pprint.pprint(data['caveats'])
        self.assertEquals(len(data['caveats']), 1)
        self.assertEquals(data['caveats'][0]['description'], "Your update is being split into 2, one for each release.")

        self.assertIn('updates', data)
        self.assertEquals(len(data['updates']), 2)


        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        # Make sure two fedmsg messages were published
        self.assertEquals(len(publish.call_args_list), 2)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_update_bugs(self, publish, *args):
        build = 'bodhi-2.0.0-2.fc17'
        args = self.get_update('bodhi-2.0.0-2.fc17')
        args['bugs'] = '56789'
        r = self.app.post_json('/updates/', args)
        self.assertEquals(len(r.json['bugs']), 1)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Pretend it was pushed to testing
        update = self.db.query(Update).filter_by(title=build).one()
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.flush()

        # Mark it as testing
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        args['bugs'] = '56789,98765'
        r = self.app.post_json('/updates/', args)
        up = r.json_body

        self.assertEquals(len(up['bugs']), 2)
        bug_ids = [bug['bug_id'] for bug in up['bugs']]
        self.assertIn(56789, bug_ids)
        self.assertIn(98765, bug_ids)
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')

        # now remove a bug
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        args['bugs'] = '98765'
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(len(up['bugs']), 1)
        bug_ids = [bug['bug_id'] for bug in up['bugs']]
        self.assertIn(98765, bug_ids)
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_missing_update(self, publish, *args):
        """ Attempt to edit an update that doesn't exist """
        build = 'bodhi-2.0.0-2.fc17'
        edited = 'bodhi-1.0-1.fc17'
        args = self.get_update(build)
        args['edited'] = edited
        r = self.app.post_json('/updates/', args, status=400).json_body
        self.assertEquals(r['status'], 'error')
        self.assertEquals(r['errors'][0]['description'], 'Cannot find update to edit: %s' % edited)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_update_and_disable_features(self, publish, *args):
        build = 'bodhi-2.0.0-2.fc17'
        args = self.get_update('bodhi-2.0.0-2.fc17')
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = r.json_body
        self.assertEquals(up['require_testcases'], True)
        self.assertEquals(up['require_bugs'], False)
        self.assertEquals(up['stable_karma'], 3)
        self.assertEquals(up['unstable_karma'], -3)

        # Pretend it was pushed to testing
        update = self.db.query(Update).filter_by(title=build).one()
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.flush()

        # Mark it as testing
        args['edited'] = args['builds']

        # Toggle a bunch of the booleans
        args['autokarma'] = False
        args['require_testcases'] = False
        args['require_bugs'] = True

        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['status'], u'testing')
        self.assertEquals(up['request'], None)

        self.assertEquals(up['require_bugs'], True)
        self.assertEquals(up['require_testcases'], False)
        self.assertEquals(up['stable_karma'], None)
        self.assertEquals(up['unstable_karma'], None)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_update_change_type(self, publish, *args):
        build = 'bodhi-2.0.0-2.fc17'
        args = self.get_update('bodhi-2.0.0-2.fc17')
        args['type'] = 'newpackage'
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        up = r.json_body
        self.assertEquals(up['type'], u'newpackage')

        # Pretend it was pushed to testing
        update = self.db.query(Update).filter_by(title=build).one()
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.flush()

        # Mark it as testing
        args['edited'] = args['builds']
        args['type'] = 'bugfix'
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['status'], u'testing')
        self.assertEquals(up['request'], None)
        self.assertEquals(up['type'], u'bugfix')

    def test_update_meeting_requirements_present(self):
        """ Check that the requirements boolean is present in our JSON """
        res = self.app.get('/updates/bodhi-2.0-1.fc17')
        actual = res.json_body['update']['meets_testing_requirements']
        expected = False
        self.assertEquals(actual, expected)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_testing_update_reset_karma(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing and give it 2 karma
        upd = Update.get(nvr, self.db)
        upd.status = UpdateStatus.testing
        upd.request = None
        upd.karma = 2
        self.db.flush()

        # Then.. edit it and change the builds!
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        # This is what we really want to test here.
        self.assertEquals(up['karma'], 0)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_testing_update_reset_karma_with_same_tester(self, publish, *args):
        """
        Ensure that someone who gave an update karma can do it again after a reset.
        https://github.com/fedora-infra/bodhi/issues/659
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.flush()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing
        upd = Update.get(nvr, self.db)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.flush()

        # Have bob +1 it
        upd.comment(self.db, u'LGTM', author=u'bob', karma=1)
        upd = Update.get(nvr, self.db)
        self.assertEquals(upd.karma, 1)

        # Then.. edit it and change the builds!
        new_nvr = u'bodhi-2.0.0-3.fc17'
        args['edited'] = args['builds']
        args['builds'] = new_nvr
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], new_nvr)
        # This is what we really want to test here.
        self.assertEquals(up['karma'], 0)

        # Have bob +1 it again
        upd = Update.get(new_nvr, self.db)
        upd.comment(self.db, u'Ship it!', author=u'bob', karma=1)

        # Bob should be able to give karma again since the reset
        self.assertEquals(upd.karma, 1)

        # Then.. edit it and change the builds!
        newer_nvr = u'bodhi-2.0.0-4.fc17'
        args['edited'] = args['builds']
        args['builds'] = newer_nvr
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], newer_nvr)
        # This is what we really want to test here.
        self.assertEquals(up['karma'], 0)

        # Have bob +1 it again
        upd = Update.get(newer_nvr, self.db)
        upd.comment(self.db, u'Ship it!', author=u'bob', karma=1)

        # Bob should be able to give karma again since the reset
        self.assertEquals(upd.karma, 1)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_manually_push_to_stable_based_on_karma(self, publish, *args):
        """
        Test manually push to stable when autokarma is disabled
        and karma threshold is reached
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.flush()

        # Makes autokarma disabled
        # Sets stable karma to 1
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        resp = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Marks it as testing
        upd = Update.get(nvr, self.db)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.flush()

        # Checks karma threshold is reached
        # Makes sure stable karma is not None
        # Ensures Request doesn't get set to stable automatically since autokarma is disabled
        upd.comment(self.db, u'LGTM', author=u'ralph', karma=1)
        upd = Update.get(nvr, self.db)
        self.assertEquals(upd.karma, 1)
        self.assertEquals(upd.stable_karma, 1)
        self.assertEquals(upd.status, UpdateStatus.testing)
        self.assertEquals(upd.request, None)

        text = config.get('testing_approval_msg_based_on_karma')
        upd.comment(self.db, text, author=u'bodhi')

        # Checks Push to Stable text in the html page for this update
        id = 'bodhi-2.0.0-2.fc17'
        resp = self.app.get('/updates/%s' % id,
                            headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertIn('Push to Stable', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_update_with_expired_override(self, publish, *args):
        """
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.flush()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Create a new expired override
        upd = Update.get(nvr, self.db)
        override = BuildrootOverride(
                build=upd.builds[0],
                submitter=user,
                notes=u'testing',
                expiration_date=datetime.utcnow(),
                expired_date=datetime.utcnow())
        self.db.add(override)
        self.db.flush()

        # Edit it and change the builds
        new_nvr = u'bodhi-2.0.0-3.fc17'
        args['edited'] = args['builds']
        args['builds'] = new_nvr
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], new_nvr)

        # Change it back to ensure we can still reference the older build
        args['edited'] = args['builds']
        args['builds'] = nvr
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], nvr)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_submit_older_build_to_stable(self, publish, *args):
        """
        Ensure we cannot submit an older build to stable when a newer one
        already exists there.
        """
        update = self.db.query(Update).one()
        update.status = UpdateStatus.stable
        update.request = None
        self.db.flush()

        oldbuild = 'bodhi-1.0-1.fc17'

        # Create a newer build
        build = Build(nvr=oldbuild, package=update.builds[0].package)
        self.db.add(build)
        update = Update(title=oldbuild, builds=[build], type=UpdateType.bugfix,
                        request=UpdateRequest.testing, notes=u'second update',
                        user=update.user, release=update.release)
        update.karma = 3
        self.db.add(update)
        self.db.flush()

        # Try and submit an older build to stable
        resp = self.app.post_json('/updates/%s/request' % oldbuild,
                {'request': 'stable', 'csrf_token': self.get_csrf_token()},
                status=400)
        eq_(resp.json['status'], 'error')
        eq_(resp.json['errors'][0]['description'],
            "Cannot submit bodhi ('0', '1.0', '1.fc17') to stable since it is older than ('0', '2.0', '1.fc17')")

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.notifications.publish')
    def test_edit_testing_update_with_build_from_different_update(self, publish, *args):
        """
        https://github.com/fedora-infra/bodhi/issues/803
        """
        # Create an update with a build that we will try and add to another update
        nvr1 = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr1)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        # Mark it as testing
        upd = Update.get(nvr1, self.db)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.flush()

        # Create an update for a different build
        nvr2 = u'koji-2.0.0-1.fc17'
        args = self.get_update(nvr2)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        # Mark it as testing
        upd = Update.get(nvr2, self.db)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.flush()

        # Edit the nvr2 update and add nvr1
        args['edited'] = args['builds']
        args['builds'] = '%s,%s' % (nvr1, nvr2)
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body
        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'], 'Update for bodhi-2.0.0-2.fc17 already exists')

        up = Update.get(nvr2, self.db)
        self.assertEquals(up.title, nvr2)  # nvr1 shouldn't be able to be added
        self.assertEquals(up.status, UpdateStatus.testing)
        self.assertEquals(len(up.builds), 1)
        self.assertEquals(up.builds[0].nvr, nvr2)

        # nvr1 update should remain intact
        up = Update.get(nvr1, self.db)
        self.assertEquals(up.title, nvr1)
        self.assertEquals(up.status, UpdateStatus.testing)
        self.assertEquals(len(up.builds), 1)
        self.assertEquals(up.builds[0].nvr, nvr1)
