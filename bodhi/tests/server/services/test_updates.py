# -*- coding: utf-8 -*-
# Copyright 2011-2018 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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
"""This module contains tests for bodhi.server.services.updates."""
from datetime import datetime, timedelta
import copy
import textwrap
import time
import unittest

from mock import ANY
import koji
import mock
import requests
import six
from six.moves.urllib import parse as urlparse

from bodhi.server import main
from bodhi.server.config import config
from bodhi.server.models import (
    BuildrootOverride, Compose, Group, RpmPackage, ModulePackage, Release,
    ReleaseState, RpmBuild, Update, UpdateRequest, UpdateStatus, UpdateType,
    UpdateSeverity, User, TestGatingStatus)
from bodhi.server.util import call_api
from bodhi.tests.server.base import BaseTestCase, BodhiTestApp


YEAR = time.localtime().tm_year

mock_valid_requirements = {
    'target': 'bodhi.server.validators._get_valid_requirements',
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
    'target': 'bodhi.server.util.taskotron_results',
    'return_value': [{
        "outcome": "PASSED",
        "data": {},
        "testcase": {"name": "rpmlint"}
    }],
}

mock_failed_taskotron_results = {
    'target': 'bodhi.server.util.taskotron_results',
    'return_value': [{
        "outcome": "FAILED",
        "data": {},
        "testcase": {"name": "rpmlint"}
    }],
}

mock_absent_taskotron_results = {
    'target': 'bodhi.server.util.taskotron_results',
    'return_value': [],
}


class TestNewUpdate(BaseTestCase):
    """
    This class contains tests for the new_update() function.
    """
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
    @mock.patch('bodhi.server.notifications.publish')
    def test_unicode_description(self, publish, *args):
        # We don't want the new update to obsolete the existing one.
        self.db.delete(Update.query.one())
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['notes'] = u'This is wünderfül'
        r = self.app.post_json('/updates/', update)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-2.fc17')
        self.assertEquals(up['notes'], u'This is wünderfül')
        self.assertIsNotNone(up['date_submitted'])
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    def test_duplicate_build(self, *args):
        res = self.app.post_json(
            '/updates/', self.get_update([u'bodhi-2.0-2.fc17', u'bodhi-2.0-2.fc17']), status=400)
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
        assert "Required check doesn't exist" in res, res

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_no_privs(self, publish, *args):
        user = User(name=u'bodhi')
        self.db.add(user)
        self.db.commit()
        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'bodhi', session=self.db, **self.app_settings))
        update_json = self.get_update(u'bodhi-2.1-1.fc17')
        update_json['csrf_token'] = self.get_csrf_token(app)

        res = app.post_json('/updates/', update_json, status=400)

        expected_error = {
            "location": "body",
            "name": "builds",
            "description": ("bodhi is not a member of \"packager\", which is a"
                            " mandatory packager group")
        }
        assert expected_error in res.json_body['errors'], \
            res.json_body['errors']
        self.assertEquals(publish.call_args_list, [])

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_privs(self, publish, *args):
        "Ensure provenpackagers can push updates for any package"
        user = User(name=u'bodhi')
        self.db.add(user)
        self.db.commit()
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)

        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'bodhi', session=self.db, **self.app_settings))
        update = self.get_update(u'bodhi-2.1-1.fc17')
        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        res = app.post_json('/updates/', update)
        assert 'bodhi does not have commit access to bodhi' not in res, res
        build = self.db.query(RpmBuild).filter_by(nvr=u'bodhi-2.1-1.fc17').one()
        assert build.update is not None
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    def test_pkgdb_outage(self, *args):
        "Test the case where our call to the pkgdb throws an exception"
        update = self.get_update(u'bodhi-2.0-2.fc17')
        update['csrf_token'] = self.get_csrf_token()

        with mock.patch.dict('bodhi.server.validators.config',
                             {'acl_system': 'pkgdb', 'pkgdb_url': 'invalidurl'}):
            res = self.app.post_json('/updates/', update, status=400)

        assert "Unable to access the Package Database" in res, res

    @mock.patch(**mock_valid_requirements)
    def test_invalid_acl_system(self, *args):
        with mock.patch.dict(config, {'acl_system': 'null'}):
            res = self.app.post_json('/updates/', self.get_update(u'bodhi-2.0-2.fc17'),
                                     status=400)

        assert "guest does not have commit access to bodhi" in res, res

    def test_put_json_update(self):
        self.app.put_json('/updates/', self.get_update(), status=405)

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_post_json_update(self, publish, *args):
        self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-1.fc17'))
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_rpm_update(self, publish, *args):
        r = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'))
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-2.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['content_type'], u'rpm')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        # The notes are inheriting notes from the update that this update obsoleted.
        self.assertEquals(up['notes'], u'this is a test update\n\n----\n\nUseful details!')
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

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_rpm_update_unknown_build(self, publish, *args):
        with mock.patch('bodhi.server.buildsys.DevBuildsys.getBuild',
                        return_value=None):
            r = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'),
                                   status=400)
            up = r.json_body

        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'],
                          "Build does not exist: bodhi-2.0.0-2.fc17")

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_rpm_update_koji_error(self, publish, *args):
        with mock.patch('bodhi.server.buildsys.DevBuildsys.getBuild',
                        side_effect=koji.GenericError()):
            r = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'),
                                   status=400)
            up = r.json_body

        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'],
                          "Koji error getting build: bodhi-2.0.0-2.fc17")

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_koji_config_url(self, publish, *args):
        """
        Test html rendering of default build link
        """
        self.app.app.registry.settings['koji_web_url'] = u'https://koji.fedoraproject.org/koji/'
        nvr = u'bodhi-2.0.0-2.fc17'
        resp = self.app.post_json('/updates/', self.get_update(nvr))

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        self.assertRegexpMatches(str(resp), ('https://koji.fedoraproject.org/koji'
                                             '/search\?terms=.*\&amp;type=build\&amp;match=glob'))

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_koji_config_url_without_trailing_slash(self, publish, *args):
        """
        Test html rendering of default build link without trailing slash
        """
        self.app.app.registry.settings['koji_web_url'] = u'https://koji.fedoraproject.org/koji'
        nvr = u'bodhi-2.0.0-2.fc17'
        resp = self.app.post_json('/updates/', self.get_update(nvr))

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        self.assertRegexpMatches(str(resp), ('https://koji.fedoraproject.org/koji'
                                             '/search\?terms=.*\&amp;type=build\&amp;match=glob'))

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_koji_config_mock_url_without_trailing_slash(self, publish, *args):
        """
        Test html rendering of build link using a mock config variable 'koji_web_url'
        without a trailing slash in it
        """
        self.app.app.registry.settings['koji_web_url'] = u'https://host.org'
        nvr = u'bodhi-2.0.0-2.fc17'
        resp = self.app.post_json('/updates/', self.get_update(nvr))

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        self.assertRegexpMatches(str(resp), ('https://host.org'
                                             '/search\?terms=.*\&amp;type=build\&amp;match=glob'))

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_module_update(self, publish, *args):
        # Ensure there are no module packages in the DB to begin with.
        self.assertEquals(self.db.query(ModulePackage).count(), 0)
        self.create_release(u'27M')
        # Then, create an update for one.
        data = self.get_update('nginx-master-20170523')

        r = self.app.post_json('/updates/', data)

        up = r.json_body
        self.assertEquals(up['title'], u'nginx-master-20170523')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F27M')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['content_type'], u'module')
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

        # At the end, ensure that the right kind of package was created.
        self.assertEquals(self.db.query(ModulePackage).count(), 1)

    @mock.patch(**mock_valid_requirements)
    def test_multiple_builds_of_same_module_stream(self, *args):
        self.create_release(u'27M')

        res = self.app.post_json('/updates/', self.get_update([u'nodejs-6-20170101',
                                                               u'nodejs-6-20170202']),
                                 status=400)
        assert 'Multiple nodejs:6 builds specified' in res, res

    @mock.patch(**mock_valid_requirements)
    def test_multiple_builds_of_different_module_stream(self, *args):
        self.create_release(u'27M')

        res = self.app.post_json('/updates/', self.get_update([u'nodejs-6-20170101',
                                                               u'nodejs-8-20170202']))
        res = res.json
        assert res['request'] == 'testing'
        assert len(res['builds']) == 2
        assert res['builds'][0]['type'] == 'module'
        assert res['builds'][1]['type'] == 'module'
        assert res['builds'][0]['nvr'] == 'nodejs-6-20170101'
        assert res['builds'][1]['nvr'] == 'nodejs-8-20170202'
        assert res['title'] == 'nodejs-6-20170101 nodejs-8-20170202'

        # At the end, ensure that the right kind of packages were created.
        self.assertEquals(self.db.query(ModulePackage).count(), 2)

    @mock.patch(**mock_valid_requirements)
    def test_multiple_updates_single_module_steam(self, *args):
        # Ensure there are no module packages in the DB to begin with.
        self.assertEquals(self.db.query(ModulePackage).count(), 0)
        self.create_release(u'27M')

        # First create an update for nodejs:6
        self.app.post_json('/updates/', self.get_update(u'nodejs-6-20170101'))

        # Next create a second update for nodejs:6
        self.app.post_json('/updates/', self.get_update(u'nodejs-6-20170202'))

        # At the end, ensure that the right kind of package was created.
        self.assertEquals(self.db.query(ModulePackage).count(), 1)
        pkg = self.db.query(ModulePackage).one()
        assert pkg.name == 'nodejs:6'

        # Assert that one update obsoleted the other
        updates = self.db.query(Update).all()
        assert updates[1].title == 'nodejs-6-20170101'
        assert updates[1].status.name == 'obsolete'
        assert updates[1].request is None

        assert updates[2].title == 'nodejs-6-20170202'
        assert updates[2].status.name == 'pending'
        assert updates[2].request.name == 'testing'

    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_container_update(self, publish, *args):
        self.create_release(u'28C')
        data = self.get_update('mariadb-10.1-10.f28container')

        r = self.app.post_json('/updates/', data, status=200)

        up = r.json_body
        self.assertEquals(up['title'], u'mariadb-10.1-10.f28container')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F28C')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['content_type'], u'container')
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

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_update_with_multiple_bugs(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = ['1234', '5678']
        r = self.app.post_json('/updates/', update)
        up = r.json_body
        # This Update inherits one bug from the Update it obsoleted.
        self.assertEquals(len(up['bugs']), 3)
        self.assertEquals(up['bugs'][0]['bug_id'], 1234)
        self.assertEquals(up['bugs'][1]['bug_id'], 5678)
        self.assertEquals(up['bugs'][2]['bug_id'], 12345)

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_update_with_multiple_bugs_as_str(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = '1234, 5678'
        r = self.app.post_json('/updates/', update)
        up = r.json_body
        # This Update inherits one bug from the Update it obsoleted.
        self.assertEquals(len(up['bugs']), 3)
        self.assertEquals(up['bugs'][0]['bug_id'], 1234)
        self.assertEquals(up['bugs'][1]['bug_id'], 5678)
        self.assertEquals(up['bugs'][2]['bug_id'], 12345)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_update_with_invalid_bugs_as_str(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = '1234, blargh'
        r = self.app.post_json('/updates/', update, status=400)
        up = r.json_body
        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'],
                          "Invalid bug ID specified: [u'1234', u'blargh']")

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_existing_build(self, *args):
        """Test submitting a new update with a build already in the database"""
        package = RpmPackage.get(u'bodhi')
        self.db.add(RpmBuild(nvr=u'bodhi-2.0.0-3.fc17', package=package))
        self.db.commit()

        args = self.get_update(u'bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)

        self.assertEqual(resp.json['title'], 'bodhi-2.0.0-3.fc17')

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_existing_package(self, *args):
        """Test submitting a new update with a package that is already in the database."""
        package = RpmPackage(name=u'existing-package')
        self.db.add(package)
        self.db.commit()
        args = self.get_update(u'existing-package-2.4.1-5.fc17')

        resp = self.app.post_json('/updates/', args)

        self.assertEqual(resp.json['title'], 'existing-package-2.4.1-5.fc17')
        package = self.db.query(RpmPackage).filter_by(name=u'existing-package').one()
        self.assertEqual(package.name, 'existing-package')

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_missing_package(self, *args):
        """Test submitting a new update with a package that is not already in the database."""
        args = self.get_update(u'missing-package-2.4.1-5.fc17')

        resp = self.app.post_json('/updates/', args)

        self.assertEqual(resp.json['title'], 'missing-package-2.4.1-5.fc17')
        package = self.db.query(RpmPackage).filter_by(name=u'missing-package').one()
        self.assertEqual(package.name, 'missing-package')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_cascade_package_requirements_to_update(self, publish, *args):

        package = self.db.query(RpmPackage).filter_by(name=u'bodhi').one()
        package.requirements = u'upgradepath rpmlint'
        self.db.commit()

        args = self.get_update(u'bodhi-2.0.0-3.fc17')
        # Don't specify any requirements so that they cascade from the package
        del args['requirements']
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        self.assertTrue('upgradepath' in up['requirements'])
        self.assertTrue('rpmlint' in up['requirements'])
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsoletion(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
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
        expected_comment = (
            u'This update has obsoleted [bodhi-2.0.0-2.fc17]({}), '
            u'and has inherited its bugs and notes.')
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-033713b73b'.format(datetime.now().year)))
        self.assertEquals(r['comments'][-1]['text'], expected_comment)
        publish.assert_called_with(
            topic='update.request.testing', msg=mock.ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.obsolete)
        expected_comment = u'This update has been obsoleted by [bodhi-2.0.0-3.fc17]({}).'
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-53345602d5'.format(datetime.now().year)))
        self.assertEquals(up.comments[-1].text, expected_comment)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.services.updates.Update.new', side_effect=IOError('oops!'))
    def test_unexpected_exception(self, publish, *args):
        """Ensure that an unexpected Exception is handled by new_update()."""
        update = self.get_update('bodhi-2.3.2-1.fc17')

        r = self.app.post_json('/updates/', update, status=400)

        self.assertEquals(r.json_body['status'], 'error')
        self.assertEquals(r.json_body['errors'][0]['description'],
                          "Unable to create update.  oops!")
        # Despite the Exception, the RpmBuild should still exist in the database
        build = self.db.query(RpmBuild).filter(RpmBuild.nvr == u'bodhi-2.3.2-1.fc17').one()
        self.assertEqual(build.package.name, 'bodhi')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.services.updates.Update.obsolete_older_updates',
                side_effect=RuntimeError("bet you didn't see this coming!"))
    def test_obsoletion_with_exception(self, *args):
        """
        Assert that an exception during obsoletion is properly handled.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with mock.patch(**mock_uuid4_version1):
            self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.testing
        up.request = None
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with mock.patch(**mock_uuid4_version2):
            r = self.app.post_json('/updates/', args).json_body

        self.assertEquals(r['request'], 'testing')
        # The exception handler should have put an error message in the caveats.
        self.assertEquals(r['caveats'][0]['description'],
                          "Problem obsoleting older updates: bet you didn't see this coming!")
        # Check for the comment multiple ways. The comment will be about the update being submitted
        # for testing instead of being about the obsoletion, since the obsoletion failed.
        # Note that caveats above don't support markdown, but comments do.
        expected_comment = 'This update has been submitted for testing by guest. '
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'], '/updates/FEDORA-2016-033713b73b'))
        self.assertEquals(r['comments'][-1]['text'], expected_comment)
        up = self.db.query(Update).filter_by(title=nvr).one()
        # The old update failed to get obsoleted.
        self.assertEquals(up.status, UpdateStatus.testing)
        expected_comment = u'This update has been submitted for testing by guest. '
        self.assertEquals(up.comments[-1].text, expected_comment)


class TestSetRequest(BaseTestCase):
    """
    This class contains tests for the set_request() function.
    """
    @mock.patch(**mock_valid_requirements)
    def test_set_request_locked_update(self, *args):
        """Ensure that we get an error if trying to set request of a locked update"""
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = True

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        self.assertEquals(res.json_body['status'], 'error')
        self.assertEquals(res.json_body[u'errors'][0][u'description'],
                          "Can't change request on a locked update")

    @mock.patch(**mock_valid_requirements)
    def test_set_request_archived_release(self, *args):
        """Ensure that we get an error if trying to setrequest of a update in an archived release"""
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False
        up.release.state = ReleaseState.archived

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        self.assertEquals(res.json_body['status'], 'error')
        self.assertEquals(res.json_body[u'errors'][0][u'description'],
                          "Can't change request for an archived release")

    @mock.patch.dict(config, {'test_gating.required': True})
    def test_test_gating_status_failed(self):
        """If the update's test_gating_status is failed, a user should not be able to push."""
        nvr = u'bodhi-2.0-1.fc17'
        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False
        up.requirements = ''
        up.test_gating_status = TestGatingStatus.failed
        up.date_testing = datetime.utcnow() - timedelta(days=8)
        up.request = None
        post_data = dict(update=nvr, request='stable', csrf_token=self.get_csrf_token())

        res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up.request, None)
        self.assertEquals(res.json_body['status'], 'error')
        self.assertEquals(res.json_body[u'errors'][0][u'description'],
                          "Requirement not met Required tests did not pass on this update")

    @mock.patch.dict(config, {'test_gating.required': True})
    def test_test_gating_status_passed(self):
        """If the update's test_gating_status is passed, a user should be able to push."""
        nvr = u'bodhi-2.0-1.fc17'
        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False
        up.requirements = ''
        up.test_gating_status = TestGatingStatus.passed
        up.date_testing = datetime.utcnow() - timedelta(days=8)
        post_data = dict(update=nvr, request='stable', csrf_token=self.get_csrf_token())

        res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=200)

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up.request, UpdateRequest.stable)
        self.assertEqual(res.json['update']['request'], 'stable')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.services.updates.Update.set_request',
                side_effect=IOError('IOError. oops!'))
    @mock.patch('bodhi.server.services.updates.Update.check_requirements',
                return_value=(True, "a fake reason"))
    @mock.patch('bodhi.server.services.updates.log.exception')
    def test_unexpected_exception(self, log_exception, check_requirements, send_request, *args):
        """Ensure that an unexpected Exception is handled by set_request()."""
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False
        up.release.state = ReleaseState.current

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        self.assertEquals(res.json_body['status'], 'error')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          u'IOError. oops!')
        log_exception.assert_called_once_with("Unhandled exception in set_request")


class TestEditUpdateForm(BaseTestCase):

    def test_edit_with_permission(self):
        """
        Test a logged in User with permissions on the update can see the form
        """
        resp = self.app.get(
            '/updates/FEDORA-{}-a3bbe1a8f2/edit'.format(datetime.utcnow().year),
            headers={'accept': 'text/html'})
        self.assertIn('Editing an update requires JavaScript', resp)

    def test_edit_without_permission(self):
        """
        Test a logged in User without permissions on the update can't see the form
        """
        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'anonymous', session=self.db, **self.app_settings))

        resp = app.get(
            '/updates/FEDORA-{}-a3bbe1a8f2/edit'.format(datetime.utcnow().year), status=400,
            headers={'accept': 'text/html'})
        self.assertIn(
            'anonymous is not a member of "packager", which is a mandatory packager group', resp)

    def test_edit_not_loggedin(self):
        """
        Test a non logged in User can't see the form
        """
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = BodhiTestApp(main({}, session=self.db, **anonymous_settings))
        resp = app.get('/updates/FEDORA-2017-a3bbe1a8f2/edit', status=403,
                       headers={'accept': 'text/html'})
        self.assertIn('<h1>403 <small>Forbidden</small></h1>', resp)
        self.assertIn('<p class="lead">Access was denied to this resource.</p>', resp)


class TestUpdatesService(BaseTestCase):

    def test_content_type(self):
        """Assert that the content type is displayed in the update template."""
        res = self.app.get('/updates/bodhi-2.0-1.fc17', status=200, headers={'Accept': 'text/html'})

        self.assertTrue(
            ('<strong>Content Type</strong>\n                </div>\n                <div>\n'
             '                  RPM') in res.text)

    def test_content_type_none(self):
        """Assert that the content type being None doesn't blow up the update template."""
        u = Update.query.filter(Update.title == u'bodhi-2.0-1.fc17').one()
        u.builds = []
        self.db.commit()
        res = self.app.get('/updates/bodhi-2.0-1.fc17', status=200, headers={'Accept': 'text/html'})

        self.assertTrue('RPM' not in res.text)

    def test_home_html_legal(self):
        """Test the home page HTML when a legal link is configured."""
        with mock.patch.dict(
                self.app.app.registry.settings, {'legal_link': 'http://loweringthebar.net/'}):
            resp = self.app.get('/', headers={'Accept': 'text/html'})

        self.assertIn('Fedora Updates System', resp)
        self.assertIn('&copy;', resp)
        self.assertIn('Legal</a>', resp)
        self.assertIn('http://loweringthebar.net/', resp)

    def test_home_html_no_legal(self):
        """Test the home page HTML when no legal link is configured."""
        with mock.patch.dict(self.app.app.registry.settings, {'legal_link': ''}):
            resp = self.app.get('/', headers={'Accept': 'text/html'})

        self.assertIn('Fedora Updates System', resp)
        self.assertIn('&copy;', resp)
        self.assertNotIn('Legal</a>', resp)
        self.assertNotIn('http://loweringthebar.net/', resp)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    def test_edit_add_build_from_different_release(self):
        """Editing an update that references builds from other releases should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = u'testing!!!'
        update_json['edited'] = update.title
        update_json['builds'] = update_json['builds'] + ',bodhi-3.2.0-1.fc27'
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            u'status': u'error',
            u'errors': [
                {u'description': u'Unable to determine release from build: bodhi-3.2.0-1.fc27',
                 u'location': u'body', u'name': u'builds'},
                {u'description': (
                    u"Cannot find release associated with build: bodhi-3.2.0-1.fc27, "
                    u"tags: [u'f27-updates-candidate', u'f27', u'f27-updates-testing']"),
                 u'location': u'body', u'name': u'builds'}]}
        self.assertEqual(res.json, expected_json)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    def test_edit_invalidly_tagged_build(self):
        """Editing an update that references invalidly tagged builds should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = u'testing!!!'
        update_json['edited'] = update.title
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                        return_value=[{'name': 'f17-updates'}]) as listTags:
            res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            u'status': u'error',
            u'errors': [
                {u'description': (
                    u"Invalid tag: bodhi-2.0-1.fc17 not tagged with any of the following tags "
                    u"[u'f17-updates-candidate', u'f17-updates-testing']"),
                 u'location': u'body', u'name': u'builds'}]}
        self.assertEqual(res.json, expected_json)
        listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    def test_edit_koji_error(self):
        """Editing an update that references missing builds should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = u'testing!!!'
        update_json['edited'] = update.title
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                        side_effect=koji.GenericError()) as listTags:
            res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            u'status': u'error',
            u'errors': [
                {u'description': u'Invalid koji build: bodhi-2.0-1.fc17', u'location': u'body',
                 u'name': u'builds'}]}
        self.assertEqual(res.json, expected_json)
        listTags.assert_called_once_with(update.title)

    def test_edit_untagged_build(self):
        """Editing an update that references untagged builds should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = u'testing!!!'
        update_json['edited'] = update.title
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                        return_value=[]) as listTags:
            res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            u'status': u'error',
            u'errors': [
                {u'description': u'Cannot find any tags associated with build: bodhi-2.0-1.fc17',
                 u'location': u'body', u'name': u'builds'},
                {u'description': (
                    u"Cannot find release associated with build: bodhi-2.0-1.fc17, "
                    u"tags: []"),
                 u'location': u'body', u'name': u'builds'}]}
        self.assertEqual(res.json, expected_json)
        listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    def test_locked_update_links_to_compose_html(self):
        """A locked update should display a link to the compose it is part of."""
        update = Update.query.first()
        compose = Compose.from_updates([update])[0]
        self.db.flush()

        resp = self.app.get('/updates/%s' % update.alias,
                            headers={'Accept': 'text/html'})

        locked_notice = 'This update is currently locked since {} (UTC) and cannot be modified.'
        locked_notice = locked_notice.format(update.date_locked.strftime('%Y-%m-%d %H:%M:%S'))
        self.assertIn(locked_notice, resp)
        self.assertIn('<span class="sr-only">Locked</span>', resp)
        self.assertIn('/composes/{}/{}'.format(compose.release.name, compose.request.value), resp)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_edit_anything(self, publish, *args):
        "Ensure provenpackagers can edit updates for any package"
        nvr = u'bodhi-2.1-1.fc17'

        user = User(name=u'lloyd')
        user2 = User(name=u'ralph')
        self.db.add(user)
        self.db.add(user2)  # Add a packager but not proventester
        self.db.commit()
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        group2 = self.db.query(Group).filter_by(name=u'packager').one()
        user2.groups.append(group2)

        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))
        up_data = self.get_update(nvr)
        up_data['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        res = app.post_json('/updates/', up_data)
        assert 'does not have commit access to bodhi' not in res, res
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'lloyd', session=self.db, **self.app_settings))
        update = self.get_update(nvr)
        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        update['notes'] = u'testing!!!'
        update['edited'] = nvr
        res = app.post_json('/updates/', update)
        assert 'bodhi does not have commit access to bodhi' not in res, res
        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        assert build.update is not None
        self.assertEquals(build.update.notes, u'testing!!!')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_request_privs(self, publish, *args):
        "Ensure provenpackagers can change the request for any update"
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        user2 = User(name=u'ralph')
        self.db.add(user)
        self.db.add(user2)  # Add a packager but not proventester
        self.db.add(User(name=u'someuser'))  # An unrelated user with no privs
        self.db.commit()
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        group2 = self.db.query(Group).filter_by(name=u'packager').one()
        user2.groups.append(group2)

        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))
        up_data = self.get_update(nvr)
        up_data['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        res = app.post_json('/updates/', up_data)
        assert 'does not have commit access to bodhi' not in res, res
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.passed
        self.assertEqual(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a non-provenpackager
        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))
        post_data = dict(update=nvr, request='stable',
                         csrf_token=app.get('/csrf').json_body['csrf_token'])
        res = app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure we can't push it until it meets the requirements
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(
            res.json_body['errors'][0]['description'], config.get('not_yet_tested_msg'))

        update = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(update.stable_karma, 3)
        self.assertEqual(update.locked, False)
        self.assertEqual(update.request, UpdateRequest.testing)

        # Pretend it was pushed to testing
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.commit()

        self.assertEqual(update.karma, 0)
        update.comment(self.db, u"foo", 1, u'foo')
        update = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(update.karma, 1)
        self.assertEqual(update.request, None)
        update.comment(self.db, u"foo", 1, u'bar')
        update = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(update.karma, 2)
        self.assertEqual(update.request, None)
        update.comment(self.db, u"foo", 1, u'biz')
        update = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(update.karma, 3)
        self.assertEqual(update.request, UpdateRequest.batched)

        # Set it back to testing
        update.request = UpdateRequest.testing

        # Try and submit the update to stable as a proventester
        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'bob', session=self.db, **self.app_settings))

        res = app.post_json('/updates/%s/request' % str(nvr),
                            dict(update=nvr, request='stable',
                                 csrf_token=app.get('/csrf').json_body['csrf_token']),
                            status=200)

        self.assertEqual(res.json_body['update']['request'], 'stable')

        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'bob', session=self.db, **self.app_settings))

        res = app.post_json('/updates/%s/request' % str(nvr),
                            dict(update=nvr, request='obsolete',
                                 csrf_token=app.get('/csrf').json_body['csrf_token']),
                            status=200)

        self.assertEqual(res.json_body['update']['request'], None)
        # We need to re-fetch the update from the database since the post calls committed the
        # transaction.
        update = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(update.request, None)
        self.assertEqual(update.status, UpdateStatus.obsolete)

        # Test that bob has can_edit True, provenpackager
        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'bob', session=self.db, **self.app_settings))

        res = app.get('/updates/%s' % str(nvr), status=200)
        self.assertEqual(res.json_body['can_edit'], True)

        # Test that ralph has can_edit True, they submitted it.
        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'ralph', session=self.db, **self.app_settings))

        res = app.get('/updates/%s' % str(nvr), status=200)
        self.assertEqual(res.json_body['can_edit'], True)

        # Test that someuser has can_edit False, they are unrelated
        # This check *failed* with the old acls code.
        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, testing=u'someuser', session=self.db, **self.app_settings))

        res = app.get('/updates/%s' % str(nvr), status=200)
        self.assertEqual(res.json_body['can_edit'], False)

        # Test that an anonymous user has can_edit False, obv.
        # This check *crashed* with the code on 2015-09-24.
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })

        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main({}, session=self.db, **anonymous_settings))

        res = app.get('/updates/%s' % str(nvr), status=200)
        self.assertEqual(res.json_body['can_edit'], False)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_request_update_queued_in_test_gating(self, publish, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `queued`"""
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        res = self.app.post_json('/updates/', up_data)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.queued
        self.assertEqual(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure we can't push it until it passed test gating
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(
            res.json_body['errors'][0]['description'],
            'Requirement not met Required tests did not pass on this update')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_request_update_running_in_test_gating(self, publish, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `running`"""
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        res = self.app.post_json('/updates/', up_data)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.running
        self.assertEqual(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure we can't push it until it passed test gating
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(
            res.json_body['errors'][0]['description'],
            'Requirement not met Required tests did not pass on this update')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_request_update_failed_test_gating(self, publish, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `failed`"""
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        res = self.app.post_json('/updates/', up_data)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.failed
        self.assertEqual(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure we can't push it until it passed test gating
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(
            res.json_body['errors'][0]['description'],
            'Requirement not met Required tests did not pass on this update')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_request_update_ignored_by_test_gating(self, publish, *args):
        """Ensure provenpackagers can request changes for any update which
        test gating status is `ignored`"""
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        res = self.app.post_json('/updates/', up_data)
        assert 'does not have commit access to bodhi' not in res, res
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.ignored
        self.assertEqual(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure the reason we cannot push isn't test gating this time
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(
            res.json_body['errors'][0]['description'],
            config.get('not_yet_tested_msg'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_request_update_waiting_on_test_gating(self, publish, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `waiting`"""
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        res = self.app.post_json('/updates/', up_data)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.waiting
        self.assertEqual(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure we can't push it until it passed test gating
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(
            res.json_body['errors'][0]['description'],
            'Requirement not met Required tests did not pass on this update')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_provenpackager_request_update_with_none_test_gating(self, publish, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `None`"""
        nvr = u'bodhi-2.1-1.fc17'
        user = User(name=u'bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        res = self.app.post_json('/updates/', up_data)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = None
        self.assertEqual(build.update.request, UpdateRequest.testing)

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json('/updates/%s/request' % str(nvr), post_data, status=400)

        # Ensure the reason we can't push is not test gating
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(
            res.json_body['errors'][0]['description'],
            config.get('not_yet_tested_msg'))

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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

    def test_404(self):
        self.app.get('/a', status=404)

    def test_get_single_update(self):
        res = self.app.get('/updates/bodhi-2.0-1.fc17', headers={'Accept': 'application/json'})
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

    def test_get_single_update_html_no_privacy_link(self):
        """Test getting a single update via HTML when no privacy link is configured."""
        id = 'bodhi-2.0-1.fc17'

        with mock.patch.dict(self.app.app.registry.settings, {'privacy_link': ''}):
            resp = self.app.get('/updates/%s' % id,
                                headers={'Accept': 'text/html'})

        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertIn('&copy;', resp)
        # The privacy policy comment should not be written on the page since by default Bodhi
        # doesn't have a configured privacy policy.
        self.assertNotIn('privacy', resp)

    def test_get_single_update_html_privacy_link(self):
        """Test getting a single update via HTML when a privacy link is configured."""
        id = 'bodhi-2.0-1.fc17'

        with mock.patch.dict(
                self.app.app.registry.settings, {'privacy_link': 'https://privacyiscool.com'}):
            resp = self.app.get('/updates/%s' % id,
                                headers={'Accept': 'text/html'})

        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertIn('&copy;', resp)
        # The privacy policy comment should not be written on the page since by default Bodhi
        # doesn't have a configured privacy policy.
        self.assertIn('Privacy policy', resp)
        self.assertIn('https://privacyiscool.com', resp)
        self.assertIn('Comments are governed under', resp)

    def test_list_updates(self):
        res = self.app.get('/updates/')
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        alias = u'FEDORA-%s-a3bbe1a8f2' % YEAR

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['submitter'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['content_type'], u'rpm')
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], alias)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(up['url'],
                          (urlparse.urljoin(config['base_address'], '/updates/%s' % alias)))

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

    def test_updates_like(self):
        res = self.app.get('/updates/', {'like': 'odh'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

        res = self.app.get('/updates/', {'like': 'wat'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_updates_search(self):
        """
        Test that the updates/?search= endpoint works as expected
        """

        # test that the search works
        res = self.app.get('/updates/', {'search': 'bodh'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

        # test that the search is case insensitive
        res = self.app.get('/updates/', {'search': 'Bodh'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

        # test a search that yields nothing
        res = self.app.get('/updates/', {'search': 'wat'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # test a search for an alias
        res = self.app.get(
            '/updates/', {'search': 'FEDORA-{}-a3bbe1a8f2'.format(datetime.utcnow().year)})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

        # test that the search works for leading space
        res = self.app.get('/updates/', {'search': ' bodh'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

        # test that the search works for trailing space
        res = self.app.get('/updates/', {'search': 'bodh '})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

        # test that the search works for both leading and trailing space
        res = self.app.get('/updates/', {'search': ' bodh '})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch(**mock_valid_requirements)
    def test_list_updates_pagination(self, *args):

        # First, stuff a second update in there
        self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'))

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
        self.db.commit()

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
        self.assertEquals(up['content_type'], u'rpm')
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.db.commit()

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
        self.assertEquals(up['content_type'], u'rpm')
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

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
        res = self.app.get('/updates/', {"submitted_since": "11-01-1984"}, status=400)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_date_submitted_before_invalid_date(self):
        """test filtering by submitted before date with an invalid date"""
        res = self.app.get('/updates/', {"submitted_before": "11-01-1984"}, status=400)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_locked(self):
        Update.query.one().locked = True
        self.db.flush()
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
        self.assertEquals(up['severity'], u'medium')
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

    def test_list_updates_by_content_type(self):
        res = self.app.get('/updates/', {"content_type": "module"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        res = self.app.get('/updates/', {"content_type": "rpm"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

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
        self.db.commit()

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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.db.commit()

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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.db.commit()

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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['locked'], False)
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
        self.db.commit()

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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_singular_release_param(self):
        """
        Test the singular parameter "release" rather than "releases".
        Note that "release" is purely for bodhi1 compat (mostly RSS feeds)
        """
        res = self.app.get('/updates/', {"release": "F17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    def test_list_updates_by_unexisting_request(self):
        res = self.app.get('/updates/', {"request": "impossible"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'request')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          u'"impossible" is not one of revoke, testing,'
                          ' obsolete, batched, stable, unpush')

    def test_list_updates_by_severity(self):
        res = self.app.get('/updates/', {"severity": "medium"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_status_active_release(self):
        res = self.app.get(
            '/updates/', {"status": "pending", "active_releases": 'true'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    def test_list_updates_by_status_inactive_release(self):
        rel = self.db.query(Release).filter_by(name='F17').one()
        rel.state = ReleaseState.archived
        self.db.commit()

        res = self.app.get(
            '/updates/', {"status": "pending", "active_releases": 'true'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    def test_list_updates_by_unexisting_status(self):
        res = self.app.get('/updates/', {"status": "single"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'status')
        self.assertEquals(
            res.json_body['errors'][0]['description'],
            ('"single" is not one of testing, side_tag_expired, processing, obsolete, '
             'pending, stable, unpushed, side_tag_active'))

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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], u'FEDORA-%s-a3bbe1a8f2' % YEAR)
        self.assertEquals(up['karma'], 1)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
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
        self.assertEquals(up['severity'], u'medium')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['locked'], False)
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

    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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

        Karma has been reset.
        """).strip()
        self.assertMultiLineEqual(up['comments'][-1]['text'], comment)
        self.assertEquals(len(up['builds']), 1)
        self.assertEquals(up['builds'][0]['nvr'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(self.db.query(RpmBuild).filter_by(nvr=u'bodhi-2.0.0-2.fc17').first(),
                          None)
        self.assertEquals(len(publish.call_args_list), 2)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_testing_update_with_new_builds(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing
        upd = Update.get(nvr)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.commit()

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

        Karma has been reset.
        """).strip()
        self.assertMultiLineEqual(up['comments'][-2]['text'], comment)
        self.assertEquals(up['comments'][-4]['text'],
                          u'This update has been submitted for testing by guest. ')
        self.assertEquals(len(up['builds']), 1)
        self.assertEquals(up['builds'][0]['nvr'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(self.db.query(RpmBuild).filter_by(nvr=u'bodhi-2.0.0-2.fc17').first(),
                          None)
        self.assertEquals(len(publish.call_args_list), 3)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_testing_update_with_new_builds_with_stable_request(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing
        upd = Update.get(nvr)
        upd.status = UpdateStatus.testing
        upd.request = UpdateRequest.stable
        self.db.commit()

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

        Karma has been reset.
        """).strip()
        self.assertMultiLineEqual(up['comments'][-2]['text'], comment)
        self.assertEquals(up['comments'][-4]['text'],
                          u'This update has been submitted for testing by guest. ')
        self.assertEquals(len(up['builds']), 1)
        self.assertEquals(up['builds'][0]['nvr'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(self.db.query(RpmBuild).filter_by(nvr=u'bodhi-2.0.0-2.fc17').first(),
                          None)
        self.assertEquals(len(publish.call_args_list), 3)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_update_with_different_release(self, publish, *args):
        """Test editing an update for one release with builds from another."""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(u'bodhi-2.0.0-2.fc17')
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
            pending_signing_tag=u'f18-updates-testing-signing',
            pending_testing_tag=u'f18-updates-testing-pending',
            pending_stable_tag=u'f18-updates-pending',
            override_tag=u'f18-override',
            branch=u'f18')
        self.db.add(release)
        pkg = RpmPackage(name=u'nethack')
        self.db.add(pkg)
        self.db.commit()

        args = self.get_update('bodhi-2.0.0-2.fc17,nethack-4.0.0-1.fc18')
        args['edited'] = nvr
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body

        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'],
                          'Cannot add a F18 build to an F17 update')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_stable_update(self, publish, *args):
        """Make sure we can't edit stable updates"""
        self.assertEquals(publish.call_args_list, [])

        # First, create a testing update
        nvr = u'bodhi-2.0.0-2.fc17'
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
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_locked_update(self, publish, *args):
        """Make sure some changes are prevented"""
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args, status=200)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = True
        up.status = UpdateStatus.testing
        up.request = None
        up_id = up.id

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
        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        self.assertEquals(up.builds, [build])

        # Changing the request should fail
        args['notes'] = 'Still new notes'
        args['builds'] = args['edited']
        args['request'] = 'stable'
        r = self.app.post_json('/updates/', args, status=400).json_body
        self.assertEquals(r['status'], 'error')
        self.assertIn('errors', r)
        self.assertIn(
            {u'description': u"Can't change the request on a locked update", u'location': u'body',
             u'name': u'builds'},
            r['errors'])
        up = self.db.query(Update).get(up_id)
        self.assertEquals(up.notes, 'Some new notes')
        # We need to re-retrieve the build since we started a new transaction in the call to
        # /updates
        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        self.assertEquals(up.builds, [build])
        self.assertEquals(up.request, None)

        # At the end of the day, two fedmsg messages should have gone out.
        self.assertEquals(len(publish.call_args_list), 2)
        publish.assert_called_with(topic='update.edit', msg=ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_pending_update_on_stable_karma_reached_autopush_enabled(self, publish, *args):
        """Ensure that a pending update stays in testing if it hits stable karma while pending."""
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2
        self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.pending
        self.db.commit()

        up.comment(self.db, u'WFM', author=u'dustymabe', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        up.comment(self.db, u'LGTM', author=u'bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        self.assertEquals(up.karma, 2)
        self.assertEquals(up.request, UpdateRequest.testing)
        self.assertEquals(up.status, UpdateStatus.pending)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_pending_urgent_update_on_stable_karma_reached_autopush_enabled(self, publish, *args):
        """
        Ensure that a pending urgent update directly requests for stable if
        it hits stable karma before reaching testing state.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2
        args['severity'] = 'urgent'
        self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.pending
        self.db.commit()

        up.comment(self.db, u'WFM', author=u'dustymabe', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        up.comment(self.db, u'LGTM', author=u'bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        self.assertEquals(up.karma, 2)
        self.assertEquals(up.request, UpdateRequest.stable)
        self.assertEquals(up.status, UpdateStatus.pending)

    @mock.patch(**mock_valid_requirements)
    def test_pending_update_on_stable_karma_not_reached(self, publish, *args):
        """ Ensure that pending update does not directly request for stable
        if it does not hit stable karma before reaching testing state """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2
        self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.pending
        self.db.commit()

        up.comment(self.db, u'WFM', author=u'dustymabe', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        self.assertEquals(up.karma, 1)
        self.assertEquals(up.request, UpdateRequest.testing)
        self.assertEquals(up.status, UpdateStatus.pending)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_pending_update_on_stable_karma_reached_autopush_disabled(self, publish, *args):
        """ Ensure that pending update has option to request for stable directly
        if it hits stable karma before reaching testing state """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 2
        args['unstable_karma'] = -2
        self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.pending
        self.db.commit()

        up.comment(self.db, u'WFM', author=u'dustymabe', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        up.comment(self.db, u'LGTM', author=u'bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        self.assertEquals(up.karma, 2)
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.testing)

        text = six.text_type(config.get('testing_approval_msg_based_on_karma'))
        up.comment(self.db, text, author=u'bodhi')
        self.assertIn('pushed to stable now if the maintainer wishes', up.comments[-1]['text'])

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsoletion_locked_with_open_request(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = True
        self.db.commit()

        args = self.get_update('bodhi-2.0.0-3.fc17')
        r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.testing)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsoletion_unlocked_with_open_request(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args)

        args = self.get_update('bodhi-2.0.0-3.fc17')
        r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.obsolete)
        self.assertEquals(up.request, None)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsoletion_unlocked_with_open_stable_request(self, publish, *args):
        """ Ensure that we don't obsolete updates that have a stable request """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = UpdateRequest.stable
        self.db.commit()

        args = self.get_update('bodhi-2.0.0-3.fc17')
        r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.stable)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_stable_for_obsolete_update(self, publish, *args):
        """
        Obsolete update should not be submitted to testing
        Test Push to Stable option for obsolete update
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with mock.patch(**mock_uuid4_version1):
            self.app.post_json('/updates/', args)
        publish.assert_called_once_with(
            topic='update.request.testing', msg=mock.ANY)
        publish.call_args_list = []

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.testing
        up.request = None

        new_nvr = u'bodhi-2.0.0-3.fc17'
        args = self.get_update(new_nvr)
        with mock.patch(**mock_uuid4_version2):
            r = self.app.post_json('/updates/', args).json_body
        self.assertEquals(r['request'], 'testing')
        publish.assert_called_with(
            topic='update.request.testing', msg=mock.ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.obsolete)
        expected_comment = u'This update has been obsoleted by [bodhi-2.0.0-3.fc17]({}).'
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-53345602d5'.format(datetime.now().year)))
        self.assertEquals(up.comments[-1].text, expected_comment)

        # Check Push to Stable button for obsolete update
        id = 'bodhi-2.0.0-2.fc17'
        resp = self.app.get('/updates/%s' % id,
                            headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertNotIn('Push to Stable', resp)

    @mock.patch(**mock_valid_requirements)
    def test_enabled_button_for_autopush(self, *args):
        """Test Enabled button on Update page when autopush is True"""
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        resp = self.app.post_json('/updates/', args)

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertIn('Enabled', resp)

    @mock.patch(**mock_valid_requirements)
    def test_disabled_button_for_autopush(self, *args):
        """Test Disabled button on Update page when autopush is False"""
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        resp = self.app.post_json('/updates/', args)

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertIn('Disabled', resp)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_invalid_request(self, *args):
        """Test submitting an invalid request"""
        args = self.get_update()
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'foo', 'csrf_token': self.get_csrf_token()}, status=400)
        resp = resp.json_body
        self.assertEqual(resp['status'], 'error')
        self.assertEqual(
            resp['errors'][0]['description'],
            u'"foo" is not one of revoke, testing, obsolete, batched, stable, unpush')

        # Now try with None
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': None, 'csrf_token': self.get_csrf_token()}, status=400)
        resp = resp.json_body
        self.assertEqual(resp['status'], 'error')
        self.assertEqual(resp['errors'][0]['name'], 'request')
        self.assertEqual(resp['errors'][0]['description'], 'Required')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_testing_request(self, publish, *args):
        """Test submitting a valid testing request"""
        Update.get(u'bodhi-2.0-1.fc17').locked = False

        args = self.get_update()
        args['request'] = None
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'testing', 'csrf_token': self.get_csrf_token()})
        self.assertEqual(resp.json['update']['request'], 'testing')
        self.assertEquals(publish.call_args_list, [])

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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
        self.db.commit()

        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'revoke', 'csrf_token': self.get_csrf_token()})
        self.assertEqual(resp.json['update']['request'], None)
        self.assertEqual(resp.json['update']['status'], 'testing')
        publish.assert_called_with(topic='update.request.revoke', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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
        self.db.commit()

        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'revoke', 'csrf_token': self.get_csrf_token()})
        self.assertEqual(resp.json['update']['request'], None)
        self.assertEqual(resp.json['update']['status'], 'unpushed')
        publish.assert_called_with(topic='update.request.revoke', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsolete_if_unstable_with_autopush_enabled_when_pending(self, publish, *args):
        """
        Send update to obsolete state if it reaches unstable karma on
        pending state where request is testing when Autopush is enabled. Make sure that it
        does not go to update-testing state.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 1
        args['unstable_karma'] = -1

        self.app.post_json('/updates/', args)
        up = Update.get(nvr)
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        self.db.commit()

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.karma, -1)
        self.assertEquals(up.status, UpdateStatus.obsolete)
        self.assertEquals(up.request, None)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsolete_if_unstable_with_autopush_disabled_when_pending(self, publish, *args):
        """
        Don't automatically send update to obsolete state if it reaches unstable karma on
        pending state when Autopush is disabled.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        args['unstable_karma'] = -1

        self.app.post_json('/updates/', args)
        up = Update.get(nvr)
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        self.db.commit()

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.karma, -1)
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.testing)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsolete_if_unstable_karma_not_reached_with_autopush_enabled_when_pending(
            self, publish, *args):
        """
        Don't send update to obsolete state if it does not reach unstable karma threshold
        on pending state when Autopush is enabled.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        self.app.post_json('/updates/', args)
        up = Update.get(nvr)
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        self.db.commit()

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.karma, -1)
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.testing)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsolete_if_unstable_with_autopush_enabled_when_testing(self, publish, *args):
        """
        Send update to obsolete state if it reaches unstable karma threshold on
        testing state where request is stable when Autopush is enabled. Make sure that the
        autopush remains enabled and the update does not go to stable state.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        self.app.post_json('/updates/', args)
        up = Update.get(nvr)
        up.status = UpdateStatus.testing
        up.request = UpdateRequest.stable
        self.db.commit()

        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        up.comment(self.db, u'WFM', author=u'puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        up.comment(self.db, u'It has bug', author=u'bowlofeggs', karma=-1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        up.comment(self.db, u'Still not working', author=u'bob', karma=-1)
        up = self.db.query(Update).filter_by(title=nvr).one()

        self.assertEquals(up.karma, -2)
        self.assertEquals(up.autokarma, True)
        self.assertEquals(up.status, UpdateStatus.obsolete)
        self.assertEquals(up.request, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_request_after_unpush(self, publish, *args):
        """Test request of this update after unpushing"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = UpdateRequest.stable
        self.db.commit()

        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'unpush', 'csrf_token': self.get_csrf_token()})
        self.assertEqual(resp.json['update']['request'], None)
        self.assertEqual(resp.json['update']['status'], 'unpushed')
        publish.assert_called_with(topic='update.request.unpush', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_invalid_stable_request(self, *args):
        """
        Test submitting a stable request for an update that has yet to meet the stable requirements.
        """
        Update.get(u'bodhi-2.0-1.fc17').locked = False

        args = self.get_update()
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertEqual(resp.json['status'], 'error')
        self.assertEqual(
            resp.json['errors'][0]['description'],
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
        self.db.commit()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        self.app.post_json('/updates/', args)

        up = Update.get(nvr)
        up.status = UpdateStatus.testing
        up.request = None
        self.assertEqual(len(up.builds), 1)
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()

        # Checks failure for requesting to stable push before the update reaches stable karma
        up.comment(self.db, u'Not working', author=u'ralph', karma=0)
        self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        up = Update.get(nvr)
        self.assertEquals(up.request, None)
        self.assertEquals(up.status, UpdateStatus.testing)

        # Checks Success for requesting to stable push after the update reaches stable karma
        up.comment(self.db, u'LGTM', author=u'ralph', karma=1)
        self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=200)
        up = Update.get(nvr)
        self.assertEquals(up.request, UpdateRequest.stable)
        self.assertEquals(up.status, UpdateStatus.testing)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_stable_request_after_testing(self, publish, *args):
        """
        Test submitting a stable request to an update that has met the minimum amount of time in
        testing.
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, u'This update has been pushed to testing', author=u'bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        self.assertEqual(len(up.builds), 1)
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()
        self.assertEqual(up.days_in_testing, 7)
        self.assertEqual(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()})
        self.assertEqual(resp.json['update']['request'], 'stable')
        publish.assert_called_with(
            topic='update.request.stable', msg=mock.ANY)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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
        self.assertEqual(len(up.builds), 1)
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'testing', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertEqual(resp.json['status'], 'error')
        self.assertEqual(
            resp.json['errors'][0]['description'],
            "Can't change request for an archived release")

    @mock.patch(**mock_failed_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_stable_request_failed_taskotron_results(self, publish, *args):
        """Test submitting a stable request, but with bad taskotron results"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, u'This update has been pushed to testing', author=u'bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        self.assertEqual(len(up.builds), 1)
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()
        self.assertEqual(up.days_in_testing, 7)
        self.assertEqual(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertIn('errors', resp)
        self.assertIn('Required task', resp)

    @mock.patch(**mock_absent_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_stable_request_absent_taskotron_results(self, publish, *args):
        """Test submitting a stable request, but with absent task results"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, u'This update has been pushed to testing', author=u'bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        self.assertEqual(len(up.builds), 1)
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()
        self.assertEqual(up.days_in_testing, 7)
        self.assertEqual(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertIn('errors', resp)
        self.assertIn('No result found for', resp)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_stable_request_when_stable(self, publish, *args):
        """Test submitting a stable request to an update that already been
        pushed to stable"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.stable
        up.request = None
        up.comment(self.db, u'This update has been pushed to testing', author=u'bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=14)
        up.comment(self.db, u'This update has been pushed to stable', author=u'bodhi')
        self.assertEqual(len(up.builds), 1)
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()
        self.assertEqual(up.days_in_testing, 14)
        self.assertEqual(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'stable', 'csrf_token': self.get_csrf_token()})
        self.assertEqual(resp.json['update']['status'], 'stable')
        self.assertEqual(resp.json['update']['request'], None)
        try:
            publish.assert_called_with(
                topic='update.request.stable', msg=mock.ANY)
            assert False, "request.stable fedmsg shouldn't have fired"
        except AssertionError:
            pass

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_testing_request_when_testing(self, publish, *args):
        """Test submitting a testing request to an update that already been
        pushed to testing"""
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, u'This update has been pushed to testing', author=u'bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=14)
        self.assertEqual(len(up.builds), 1)
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()
        self.assertEqual(up.days_in_testing, 14)
        self.assertEqual(up.meets_testing_requirements, True)
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'testing', 'csrf_token': self.get_csrf_token()})
        self.assertEqual(resp.json['update']['status'], 'testing')
        self.assertEqual(resp.json['update']['request'], None)
        try:
            publish.assert_called_with(
                topic='update.request.testing', msg=mock.ANY)
            assert False, "request.testing fedmsg shouldn't have fired"
        except AssertionError:
            pass

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
        self.db.commit()

        newtitle = u'bodhi-2.0-3.fc17'
        args = self.get_update(newtitle)
        resp = self.app.post_json('/updates/', args)

        # Note that this does **not** obsolete the other update
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
        upd = self.db.query(Update).filter(Update.alias.isnot(None)).first()
        res = self.app.get('/updates/', {"alias": upd.alias})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        # We need to refetch the update since the call to /updates/ committed the transaction.
        upd = self.db.query(Update).filter(Update.alias.isnot(None)).first()
        self.assertEquals(up['title'], upd.title)
        self.assertEquals(up['alias'], upd.alias)

        res = self.app.get('/updates/', {"updateid": upd.alias})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)
        up = body['updates'][0]
        # We need to refetch the update since the call to /updates/ committed the transaction.
        upd = self.db.query(Update).filter(Update.alias.isnot(None)).first()
        self.assertEquals(up['title'], upd.title)

        res = self.app.get('/updates/', {"updateid": 'BLARG'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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
            pending_signing_tag=u'f18-updates-testing-signing',
            pending_testing_tag=u'f18-updates-testing-pending',
            pending_stable_tag=u'f18-updates-pending',
            override_tag=u'f18-override',
            branch=u'f18')
        self.db.add(release)
        pkg = RpmPackage(name=u'nethack')
        self.db.add(pkg)
        self.db.commit()

        # A multi-release submission!!!  This should create *two* updates
        args = self.get_update('bodhi-2.0.0-2.fc17,bodhi-2.0.0-2.fc18')
        r = self.app.post_json('/updates/', args)
        data = r.json_body

        self.assertIn('caveats', data)
        self.assertEquals(len(data['caveats']), 2)
        self.assertEquals(data['caveats'][0]['description'],
                          "Your update is being split into 2, one for each release.")
        self.assertEquals(
            data['caveats'][1]['description'],
            "This update has obsoleted bodhi-2.0-1.fc17, and has inherited its bugs and notes.")

        self.assertIn('updates', data)
        self.assertEquals(len(data['updates']), 2)

        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        # Make sure two fedmsg messages were published
        self.assertEquals(len(publish.call_args_list), 2)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_update_bugs(self, publish, *args):
        build = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(u'bodhi-2.0.0-2.fc17')
        args['bugs'] = '56789'
        r = self.app.post_json('/updates/', args)
        # This has two bugs because it obsoleted another update and inherited its bugs.
        self.assertEquals(len(r.json['bugs']), 2)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Pretend it was pushed to testing and tested
        update = self.db.query(Update).filter_by(title=build).one()
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.commit()

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
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_missing_update(self, publish, *args):
        """ Attempt to edit an update that doesn't exist """
        build = u'bodhi-2.0.0-2.fc17'
        edited = 'bodhi-1.0-1.fc17'
        args = self.get_update(build)
        args['edited'] = edited
        r = self.app.post_json('/updates/', args, status=400).json_body
        self.assertEquals(r['status'], 'error')
        self.assertEquals(r['errors'][0]['description'], 'Cannot find update to edit: %s' % edited)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_update_and_disable_features(self, publish, *args):
        build = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(u'bodhi-2.0.0-2.fc17')
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = r.json_body
        self.assertEquals(up['require_testcases'], True)
        self.assertEquals(up['require_bugs'], False)
        self.assertEquals(up['stable_karma'], 3)
        self.assertEquals(up['unstable_karma'], -3)

        # Pretend it was pushed to testing and tested
        update = self.db.query(Update).filter_by(title=build).one()
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.commit()

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
        self.assertEquals(up['stable_karma'], 3)
        self.assertEquals(up['unstable_karma'], -3)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_update_change_type(self, publish, *args):
        build = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(u'bodhi-2.0.0-2.fc17')
        args['type'] = 'newpackage'
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        up = r.json_body
        self.assertEquals(up['type'], u'newpackage')

        # Pretend it was pushed to testing and tested
        update = self.db.query(Update).filter_by(title=build).one()
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.commit()

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
        res = self.app.get('/updates/bodhi-2.0-1.fc17', headers={'Accept': 'application/json'})
        actual = res.json_body['update']['meets_testing_requirements']
        expected = False
        self.assertEquals(actual, expected)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_testing_update_reset_karma(self, publish, *args):
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing, tested and give it 2 karma
        upd = Update.get(nvr)
        upd.status = UpdateStatus.testing
        upd.request = None
        upd.comment(self.db, u'LGTM', author=u'bob', karma=1)
        upd.comment(self.db, u'LGTM2ME2', author=u'other_bob', karma=1)
        self.db.commit()
        self.assertEqual(upd.karma, 2)

        # Then.. edit it and change the builds!
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        # This is what we really want to test here.
        self.assertEquals(up['karma'], 0)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_testing_update_reset_karma_with_same_tester(self, publish, *args):
        """
        Ensure that someone who gave an update karma can do it again after a reset.
        https://github.com/fedora-infra/bodhi/issues/659
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Mark it as testing and as tested
        upd = Update.get(nvr)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.commit()

        # Have bob +1 it
        upd.comment(self.db, u'LGTM', author=u'bob', karma=1)
        upd = Update.get(nvr)
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
        upd = Update.get(new_nvr)
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
        upd = Update.get(newer_nvr)
        upd.comment(self.db, u'Ship it!', author=u'bob', karma=1)

        # Bob should be able to give karma again since the reset
        self.assertEquals(upd.karma, 1)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test__composite_karma_with_one_negative(self, publish, *args):
        """The test asserts that _composite_karma returns (0, -1) when an update receives one
           negative karma"""
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args).json_body
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = None
        up.status = UpdateStatus.testing
        self.db.commit()

        # The user gives negative karma first
        up.comment(self.db, u'Failed to work', author=u'luke', karma=-1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (0, -1))

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test__composite_karma_with_changed_karma(self, publish, *args):
        """
        This test asserts that _composite_karma returns (1, 0) when a user posts negative karma
        and then later posts positive karma.
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args).json_body
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = None
        up.status = UpdateStatus.testing
        self.db.commit()

        # The user gives negative karma first
        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (0, -1))

        # The same user gives positive karma later
        up.comment(self.db, u'wfm', author=u'ralph', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (1, 0))
        self.assertEquals(up.karma, 1)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test__composite_karma_with_positive_karma_first(self, publish, *args):
        """
        This test asserts that _composite_karma returns (1, -1) when one user posts positive karma
        and then another user posts negative karma.
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args).json_body
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = None
        up.status = UpdateStatus.testing
        self.db.commit()

        #  user gives positive karma first
        up.comment(self.db, u'Works for me', author=u'ralph', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (1, 0))

        # Another user gives negative karma later
        up.comment(self.db, u'Failed to work', author=u'bowlofeggs', karma=-1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (1, -1))
        self.assertEquals(up.karma, 0)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test__composite_karma_with_no_negative_karma(self, publish, *args):
        """The test asserts that _composite_karma returns (*, 0) when there is no negative karma."""
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args).json_body
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = None
        up.status = UpdateStatus.testing
        self.db.commit()

        up.comment(self.db, u'LGTM', author=u'mac', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (1, 0))

        # Karma with no comment
        up.comment(self.db, u' ', author=u'bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (2, 0))
        self.assertEquals(up.karma, 2)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test__composite_karma_with_anonymous_comment(self, publish, *args):
        """
        The test asserts that _composite_karma returns (0, 0) when an anonymous user
        gives negative karma to an update.
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args).json_body
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = None
        up.status = UpdateStatus.testing
        self.db.commit()

        up.comment(self.db, u'Not working', author='me', anonymous=True, karma=-1)
        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (0, 0))

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test__composite_karma_with_no_feedback(self, publish, *args):
        """This test asserts that _composite_karma returns (0, 0) when an update has no feedback."""
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)
        self.app.post_json('/updates/', args).json_body
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.request = None
        up.status = UpdateStatus.testing
        self.db.commit()

        up = self.db.query(Update).filter_by(title=nvr).one()
        self.assertEqual(up._composite_karma, (0, 0))

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_karma_threshold_with_disabled_autopush(self, publish, *args):
        """Ensure Karma threshold field is not None when Autopush is disabled."""
        build = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(build)
        args['autokarma'] = False
        args['stable_karma'] = 3
        args['unstable_karma'] = -3
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = r.json_body
        self.assertEquals(up['autokarma'], False)
        self.assertEquals(up['stable_karma'], 3)
        self.assertEquals(up['unstable_karma'], -3)

        # Pretend it was pushed to testing
        update = self.db.query(Update).filter_by(title=build).one()
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        self.db.commit()

        # Mark it as testing
        args['edited'] = args['builds']

        # Change Karma Thresholds
        args['stable_karma'] = 4
        args['unstable_karma'] = -4

        r = self.app.post_json('/updates/', args)
        up = r.json_body
        self.assertEquals(up['status'], u'testing')
        self.assertEquals(up['request'], None)
        self.assertEquals(up['autokarma'], False)
        self.assertEquals(up['stable_karma'], 4)
        self.assertEquals(up['unstable_karma'], -4)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_disable_autopush_for_critical_updates(self, publish, *args):
        """Make sure that autopush is disabled if a critical update receives any negative karma"""
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        resp = self.app.post_json('/updates/', args)
        self.assertTrue(resp.json['critpath'])
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        self.db.commit()

        # A user gives negative karma first
        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        # Another user gives positive karma
        up.comment(self.db, u'wfm', author=u'bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        self.assertEquals(up.karma, 0)
        self.assertEquals(up.status, UpdateStatus.testing)
        self.assertEquals(up.request, None)

        # Autopush gets disabled since there is a negative karma from ralph
        self.assertEquals(up.autokarma, False)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_autopush_critical_update_with_no_negative_karma(self, publish, *args):
        """Autopush critical update when it has no negative karma"""
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        resp = self.app.post_json('/updates/', args)
        self.assertTrue(resp.json['critpath'])
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        self.db.commit()

        up.comment(self.db, u'LGTM', author=u'ralph', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'LGTM', author=u'bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        self.assertEquals(up.karma, 2)

        # No negative karma: Update gets automatically marked as stable
        self.assertEquals(up.autokarma, True)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        self.assertEquals(up.request, UpdateRequest.batched)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_manually_push_critical_update_with_negative_karma(self, publish, *args):
        """
        Manually push critical update when it has negative karma
        Autopush gets disabled after it receives negative karma
        A user gives negative karma, but another 3 users give positive karma
        The critical update should be manually pushed because of the negative karma
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 3
        args['unstable_karma'] = -3

        resp = self.app.post_json('/updates/', args)
        self.assertTrue(resp.json['critpath'])
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        self.db.commit()

        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'LGTM', author=u'bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'wfm', author=u'luke', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'LGTM', author=u'puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'LGTM', author=u'trishnag', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        self.assertEquals(up.karma, 3)
        self.assertEquals(up.autokarma, False)
        # The request should still be at testing. This assertion tests for
        # https://github.com/fedora-infra/bodhi/issues/989 where karma comments were resetting the
        # request to None.
        self.assertEquals(up.request, UpdateRequest.testing)
        self.assertEquals(up.status, UpdateStatus.testing)

        id = 'kernel-3.11.5-300.fc17'
        resp = self.app.get('/updates/%s' % id,
                            headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_manually_push_critical_update_with_autopush_turned_off(self, publish, *args):
        """
        Manually push critical update when it has Autopush turned off
        and make sure the update doesn't get Autopushed
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 3
        args['unstable_karma'] = -3

        resp = self.app.post_json('/updates/', args)
        self.assertTrue(resp.json['critpath'])
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        self.db.commit()

        up.comment(self.db, u'LGTM Now', author=u'ralph', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'wfm', author=u'luke', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'LGTM', author=u'puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        self.assertEquals(up.karma, 3)
        self.assertEquals(up.autokarma, False)
        # The request should still be at testing. This assertion tests for
        # https://github.com/fedora-infra/bodhi/issues/989 where karma comments were resetting the
        # request to None.
        self.assertEquals(up.request, UpdateRequest.testing)
        self.assertEquals(up.status, UpdateStatus.testing)

        id = 'kernel-3.11.5-300.fc17'
        resp = self.app.get('/updates/%s' % id,
                            headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_disable_autopush_non_critical_update_with_negative_karma(self, publish, *args):
        """Disable autokarma on non-critical updates upon negative comment."""
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 3
        args['unstable_karma'] = -3

        resp = self.app.post_json('/updates/', args)
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        self.db.commit()

        up.comment(self.db, u'Failed to work', author=u'ralph', karma=-1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        expected_comment = config.get('disable_automatic_push_to_stable')
        self.assertEquals(up.comments[3].text, expected_comment)

        up.comment(self.db, u'LGTM Now', author=u'ralph', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'wfm', author=u'luke', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'LGTM', author=u'puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        self.assertEquals(up.karma, 3)
        self.assertEquals(up.autokarma, False)

        # Request and Status remains testing since the autopush is disabled
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        self.assertEquals(up.request, UpdateRequest.testing)
        self.assertEquals(up.status, UpdateStatus.testing)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_autopush_non_critical_update_with_no_negative_karma(self, publish, *args):
        """
        Make sure autopush doesn't get disabled for Non Critical update if it
        does not receive any negative karma. Test update gets automatically
        marked as batched.
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        resp = self.app.post_json('/updates/', args)
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        self.db.commit()

        up.comment(self.db, u'LGTM Now', author=u'ralph', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'WFM', author=u'puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        # No negative karma: Update gets automatically marked as stable
        self.assertEquals(up.autokarma, True)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        self.assertEquals(up.request, UpdateRequest.batched)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_button_not_present_when_stable(self, publish, *args):
        """
        Assert that the edit button is not present on stable updates.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.date_stable = datetime.utcnow()
        update.status = UpdateStatus.stable
        update.pushed = True
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Edit text not in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('Push to Batched', resp)
        self.assertNotIn('Push to Stable', resp)
        self.assertNotIn('Edit', resp)

    @mock.patch.dict('bodhi.server.models.config', {'test_gating.required': True})
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_batched_button_not_present_when_test_gating_status_failed(self, publish):
        """The push to batched button should not appear if the test_gating_status is failed."""
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['requirements'] = ''
        resp = self.app.post_json('/updates/', args, headers={'Accept': 'application/json'})
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.failed
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        self.db.commit()
        self.app.app.registry.settings['test_gating.required'] = True

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        self.assertNotIn('Push to Batched', resp)
        self.assertNotIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch.dict('bodhi.server.models.config', {'test_gating.required': True})
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_batched_button_present_when_test_gating_status_passed(self, publish):
        """The push to batched button should appear if the test_gating_status is passed."""
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['requirements'] = ''
        resp = self.app.post_json('/updates/', args, headers={'Accept': 'application/json'})
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.passed
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        self.db.commit()
        self.app.app.registry.settings['test_gating.required'] = True

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        self.assertIn('Push to Batched', resp)
        self.assertNotIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_batched_button_present_when_karma_reached(self, publish, *args):
        """
        Assert that the "Push to Batched" button appears when the required karma is
        reached.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Batched text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertIn('Push to Batched', resp)
        self.assertNotIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_stable_button_present_when_karma_reached_urgent(self, publish, *args):
        """
        Assert that the "Push to Stable" button appears when the required karma is
        reached for an urgent update.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.severity = UpdateSeverity.urgent
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('Push to Batched', resp)
        self.assertIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_stable_button_present_when_karma_reached_and_batched(self, publish, *args):
        """
        Assert that the "Push to Stable" button appears when the required karma is
        reached and the update is already batched.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = UpdateRequest.batched
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('Push to Batched', resp)
        self.assertIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_stable_button_present_when_autokarma_and_batched(self, publish, *args):
        """
        Assert that the "Push to Stable" button appears when the required karma is
        reached and the update is already batched and autokarma was enabled.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = UpdateRequest.batched
        update.pushed = True
        update.autokarma = True
        update.stable_karma = 1
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('Push to Batched', resp)
        self.assertIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_batched_button_present_when_time_reached(self, publish, *args):
        """
        Assert that the "Push to Batched" button appears when the required time in testing is
        reached.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        # This update has been in testing a while, so a "Push to Batched" button should appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Batched text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertIn('Push to Batched', resp)
        self.assertNotIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_stable_button_present_when_time_reached_and_urgent(self, publish, *args):
        """
        Assert that the "Push to Stable" button appears when the required time in testing is
        reached.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.severity = UpdateSeverity.urgent
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        # This urgent update has been in testing a while, so a "Push to Stable" button should
        # appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('Push to Batched', resp)
        self.assertIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_stable_button_present_when_time_reached_and_batched(self, publish, *args):
        """
        Assert that the "Push to Stable" button appears when the required time in testing is
        reached and the update is already batched.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = UpdateRequest.batched
        update.pushed = True
        # This update has been in testing a while, so a "Push to Stable" button should appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('Push to Batched', resp)
        self.assertIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_batched_button_present_when_time_reached_critpath(self, publish, *args):
        """
        Assert that the "Push to Batched" button appears when it should for a critpath update.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.critpath = True
        # This update has been in testing a while, so a "Push to Batched" button should appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Batched text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertIn('Push to Batched', resp)
        self.assertNotIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_to_stable_button_present_when_time_reached_and_batched_critpath(self, publish,
                                                                                  *args):
        """
        Assert that the "Push to Stable" button appears when the required time in testing is
        reached and the update is already batched.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.critpath = True
        update.status = UpdateStatus.testing
        update.request = UpdateRequest.batched
        update.pushed = True
        # This update has been in testing a while, so a "Push to Batched" button should appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('Push to Batched', resp)
        self.assertIn('Push to Stable', resp)
        self.assertIn('Edit', resp)

    def assertSeverityHTML(self, severity, text):
        """
        Assert that the "Update Severity" label appears correctly given specific 'severity'.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.severity = severity
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.date_testing = datetime.now() - timedelta(days=30)
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks correct class label and text for update severity in the html page for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertIn(text, resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_severity_label_present_correctly_when_severity_is_urgent(self, publish, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is urgent.
        """
        self.assertSeverityHTML(UpdateSeverity.urgent,
                                '<span class=\'label label-danger\'>urgent</span>')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_severity_label_present_correctly_when_severity_is_high(self, publish, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is high.
        """
        self.assertSeverityHTML(UpdateSeverity.high,
                                '<span class=\'label label-warning\'>high</span>')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_severity_label_present_correctly_when_severity_is_medium(self, publish, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is medium.
        """
        self.assertSeverityHTML(UpdateSeverity.medium,
                                '<span class=\'label label-primary\'>medium</span>')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_severity_label_present_correctly_when_severity_is_low(self, publish, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is low.
        """
        self.assertSeverityHTML(UpdateSeverity.low,
                                '<span class=\'label label-success\'>low</span>')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_severity_label_present_correctly_when_severity_is_unspecified(self, publish,
                                                                                  *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is unspecified.
        """
        self.assertSeverityHTML(UpdateSeverity.unspecified,
                                '<span class=\'label label-default\'>unspecified</span>')

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_severity_label_absent_when_severity_is_None(self, publish, *args):
        """
        Assert that the "Update Severity" label doesn't appear when severity is None
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        resp = self.app.post_json('/updates/', args)
        update = Update.get(nvr)
        update.severity = None
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.date_testing = datetime.now() - timedelta(days=30)
        self.db.commit()

        resp = self.app.get('/updates/%s' % nvr, headers={'Accept': 'text/html'})

        # Checks 'Update Severity' text is absent in the html for this update
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(nvr, resp)
        self.assertNotIn('<strong>Update Severity</strong>', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_manually_push_to_stable_based_on_karma(self, publish, *args):
        """
        Test manually push to stable when autokarma is disabled
        and karma threshold is reached
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        # Makes autokarma disabled
        # Sets stable karma to 1
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        resp = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Marks it as batched
        upd = Update.get(nvr)
        upd.status = UpdateStatus.testing
        upd.request = UpdateRequest.batched
        upd.pushed = True
        upd.date_testing = datetime.now() - timedelta(days=1)
        self.db.commit()

        # Checks karma threshold is reached
        # Makes sure stable karma is not None
        # Ensures Request doesn't get set to stable automatically since autokarma is disabled
        upd.comment(self.db, u'LGTM', author=u'ralph', karma=1)
        upd = Update.get(nvr)
        self.assertEquals(upd.karma, 1)
        self.assertEquals(upd.stable_karma, 1)
        self.assertEquals(upd.status, UpdateStatus.testing)
        self.assertEquals(upd.request, UpdateRequest.batched)
        self.assertEquals(upd.autokarma, False)
        self.assertEquals(upd.pushed, True)

        text = six.text_type(config.get('testing_approval_msg_based_on_karma'))
        upd.comment(self.db, text, author=u'bodhi')

        # Checks Push to Stable text in the html page for this update
        id = 'bodhi-2.0.0-2.fc17'
        resp = self.app.get('/updates/%s' % id,
                            headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertIn('Push to Stable', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_manually_push_to_batched_based_on_karma(self, publish, *args):
        """
        Test manually push to batched when autokarma is disabled
        and karma threshold is reached. Ensure that the option/button to push to
        stable is not present prior to entering the batched request state.
        """

        # Disabled
        # Sets stable karma to 1
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        resp = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Marks it as testing
        upd = Update.get(nvr)
        upd.status = UpdateStatus.testing
        upd.pushed = True
        upd.request = None
        upd.date_testing = datetime.now() - timedelta(days=1)
        self.db.commit()

        # Checks karma threshold is reached
        # Makes sure stable karma is not None
        # Ensures Request doesn't get set to stable automatically since autokarma is disabled
        upd.comment(self.db, u'LGTM', author=u'ralph', karma=1)
        upd = Update.get(nvr)
        self.assertEquals(upd.karma, 1)
        self.assertEquals(upd.stable_karma, 1)
        self.assertEquals(upd.status, UpdateStatus.testing)
        self.assertEquals(upd.request, None)
        self.assertEquals(upd.autokarma, False)

        text = six.text_type(config.get('testing_approval_msg_based_on_karma'))
        upd.comment(self.db, text, author=u'bodhi')

        # Checks Push to Batched text in the html page for this update
        id = 'bodhi-2.0.0-2.fc17'
        resp = self.app.get('/updates/%s' % id,
                            headers={'Accept': 'text/html'})
        self.assertIn('text/html', resp.headers['Content-Type'])
        self.assertIn(id, resp)
        self.assertIn('Push to Batched', resp)
        self.assertNotIn('Push to Stable', resp)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_update_with_expired_override(self, publish, *args):
        """
        """
        user = User(name=u'bob')
        self.db.add(user)
        self.db.commit()

        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        # Create a new expired override
        upd = Update.get(nvr)
        override = BuildrootOverride(
            build=upd.builds[0], submitter=user, notes=u'testing',
            expiration_date=datetime.utcnow(), expired_date=datetime.utcnow())
        self.db.add(override)
        self.db.commit()

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
    @mock.patch('bodhi.server.notifications.publish')
    def test_submit_older_build_to_stable(self, publish, *args):
        """
        Ensure we cannot submit an older build to stable when a newer one
        already exists there.
        """
        update = self.db.query(Update).one()
        update.status = UpdateStatus.stable
        update.request = None
        self.db.commit()

        oldbuild = u'bodhi-1.0-1.fc17'

        # Create a newer build
        build = RpmBuild(nvr=oldbuild, package=update.builds[0].package)
        self.db.add(build)
        update = Update(title=oldbuild, builds=[build], type=UpdateType.bugfix,
                        request=UpdateRequest.testing, notes=u'second update',
                        user=update.user, release=update.release)
        update.comment(self.db, u"foo1", 1, u'foo1')
        update.comment(self.db, u"foo2", 1, u'foo2')
        update.comment(self.db, u"foo3", 1, u'foo3')
        self.db.add(update)
        self.db.commit()

        # Try and submit an older build to stable
        resp = self.app.post_json(
            '/updates/%s/request' % str(oldbuild),
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        self.assertEqual(resp.json['status'], 'error')
        self.assertEqual(
            resp.json['errors'][0]['description'],
            ("Cannot submit bodhi ('0', '1.0', '1.fc17') to stable since it is older than "
             "('0', '2.0', '1.fc17')"))

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
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
        upd = Update.get(nvr1)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.commit()

        # Create an update for a different build
        nvr2 = u'koji-2.0.0-1.fc17'
        args = self.get_update(nvr2)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)
        # Mark it as testing
        upd = Update.get(nvr2)
        upd.status = UpdateStatus.testing
        upd.request = None
        self.db.commit()

        # Edit the nvr2 update and add nvr1
        args['edited'] = args['builds']
        args['builds'] = '%s,%s' % (nvr1, nvr2)
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body
        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'],
                          'Update for bodhi-2.0.0-2.fc17 already exists')

        up = Update.get(nvr2)
        self.assertEquals(up.title, nvr2)  # nvr1 shouldn't be able to be added
        self.assertEquals(up.status, UpdateStatus.testing)
        self.assertEquals(len(up.builds), 1)
        self.assertEquals(up.builds[0].nvr, nvr2)

        # nvr1 update should remain intact
        up = Update.get(nvr1)
        self.assertEquals(up.title, nvr1)
        self.assertEquals(up.status, UpdateStatus.testing)
        self.assertEquals(len(up.builds), 1)
        self.assertEquals(up.builds[0].nvr, nvr1)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_meets_testing_requirements_since_karma_reset_critpath(self, publish, *args):
        """
        Ensure a critpath update still meets testing requirements after receiving negative karma
        and after a karma reset event.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates/', args)
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        update = Update.get(nvr)
        update.status = UpdateStatus.testing
        update.request = None
        update.critpath = True
        update.autokarma = True
        update.date_testing = datetime.utcnow() + timedelta(days=-20)
        update.comment(self.db, u'lgtm', author=u'friend', karma=1)
        update.comment(self.db, u'lgtm', author=u'friend2', karma=1)
        update.comment(self.db, u'bad', author=u'enemy', karma=-1)
        self.db.commit()

        self.assertEqual(update.meets_testing_requirements, False)

        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args)
        up = r.json_body

        self.assertEquals(up['title'], u'bodhi-2.0.0-3.fc17')
        self.assertEquals(up['karma'], 0)

        update = Update.get(u'bodhi-2.0.0-3.fc17')
        update.status = UpdateStatus.testing
        self.date_testing = update.date_testing + timedelta(days=7)
        update.comment(self.db, u'lgtm', author='friend3', karma=1)
        update.comment(self.db, u'lgtm2', author='friend4', karma=1)
        self.db.commit()

        self.assertEquals(update.days_to_stable, 0)
        self.assertEqual(update.meets_testing_requirements, True)

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_batched_update(self, publish, *args):
        """
        Ensure that 'batched' is an acceptable type of update request.
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')
        resp = self.app.post_json('/updates/', args)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.pushed = True
        up.test_gating_status = TestGatingStatus.passed
        up.comment(self.db, u"foo1", 1, u'foo1')
        up.comment(self.db, u"foo2", 1, u'foo2')
        self.db.commit()

        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'batched', 'csrf_token': self.get_csrf_token()})

        self.assertEqual(resp.json['update']['request'], 'batched')
        publish.assert_called_with(
            topic='update.request.batched', msg=mock.ANY)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_newpackage_update_bypass_batched(self, publish, *args):
        """
        Make sure a newpackage update skips the 'batched' request and immediately enters stable
        upon getting the sufficient number of karma.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2

        resp = self.app.post_json('/updates/', args)
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.type = UpdateType.newpackage
        self.db.commit()

        up.comment(self.db, u'cool beans', author=u'mrgroovy', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'lgtm', author=u'caleigh', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        self.assertEquals(up.request, UpdateRequest.stable)

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_urgent_update_bypass_batched(self, publish, *args):
        """
        Make sure an urgent update skips the 'batched' request and immediately enters stable
        upon getting the sufficient number of karma.
        """
        nvr = u'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2

        resp = self.app.post_json('/updates/', args)
        self.assertEquals(resp.json['request'], 'testing')
        publish.assert_called_with(topic='update.request.testing', msg=ANY)

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        up.status = UpdateStatus.testing
        up.severity = UpdateSeverity.urgent
        self.db.commit()

        up.comment(self.db, u'cool beans', author=u'mrgroovy', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up.comment(self.db, u'lgtm', author=u'caleigh', karma=1)
        up = self.db.query(Update).filter_by(title=resp.json['title']).one()

        up = self.db.query(Update).filter_by(title=resp.json['title']).one()
        self.assertEquals(up.request, UpdateRequest.stable)


class TestWaiveTestResults(BaseTestCase):
    """
    This class contains tests for the waive_test_results() function.
    """
    def test_cannot_waive_test_results_on_locked_update(self, *args):
        """Ensure that we get an error if trying to waive test results of a locked update"""
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = True

        post_data = dict(update=nvr,
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json('/updates/%s/waive-test-results' % str(nvr), post_data, status=400)

        self.assertEquals(res.json_body['status'], 'error')
        self.assertEquals(res.json_body[u'errors'][0][u'description'],
                          "Can't waive test results on a locked update")

    def test_cannot_waive_test_results_when_test_gating_is_off(self, *args):
        """
        Ensure that we get an error if trying to waive test results of an update
        when test gating is off.
        """
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False

        post_data = dict(update=nvr,
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json('/updates/%s/waive-test-results' % str(nvr), post_data, status=400)

        self.assertEquals(res.json_body['status'], 'error')
        self.assertEquals(res.json_body[u'errors'][0][u'description'],
                          "Test gating is not enabled")

    @mock.patch('bodhi.server.services.updates.Update.waive_test_results',
                side_effect=IOError('IOError. oops!'))
    @mock.patch('bodhi.server.services.updates.log.exception')
    def test_unexpected_exception(self, log_exception, waive_test_results, *args):
        """Ensure that an unexpected Exception is handled by waive_test_results()."""
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json('/updates/%s/waive-test-results' % str(nvr), post_data, status=400)

        self.assertEquals(res.json_body['status'], 'error')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          u'IOError. oops!')
        log_exception.assert_called_once_with("Unhandled exception in waive_test_results")


class TestGetTestResults(BaseTestCase):
    """
    This class contains tests for the get_test_results() function.
    """
    @mock.patch.dict(config, [('greenwave_api_url', None)])
    def test_cannot_get_test_results_when_no_greenwave_url(self, *args):
        """
        Ensure that we get an error if trying to get test results of an update
        when there is no greenwave_api_url defined in the configuration.
        """
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False

        res = self.app.get('/updates/%s/get-test-results' % str(nvr), status=501)

        self.assertEqual(res.status_code, 501)
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(res.json_body[u'errors'][0][u'description'],
                         "No greenwave_api_url specified")

    @mock.patch('bodhi.server.services.updates.Update.get_test_gating_info',
                side_effect=IOError('IOError. oops!'))
    @mock.patch('bodhi.server.services.updates.log.exception')
    def test_unexpected_exception(self, log_exception, get_test_gating_info, *args):
        """Ensure that an unexpected Exception is handled by get_test_results()."""
        nvr = u'bodhi-2.0-1.fc17'

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False

        res = self.app.get('/updates/%s/get-test-results' % str(nvr), status=500)

        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json_body['status'], 'error')
        self.assertEqual(res.json_body['errors'][0]['description'],
                         u'IOError. oops!')
        log_exception.assert_called_once_with("Unhandled exception in get_test_results")

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_erroring_on_greenwave(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument but that call raises an error.
        """
        nvr = u'bodhi-2.0-1.fc17'
        call_api.side_effect = requests.exceptions.HTTPError(
            'Un-expected error foo bar')

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False

        res = self.app.get('/updates/%s/get-test-results' % str(nvr), status=502)

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': u'fedora-17',
                'decision_context': u'bodhi_update_push_testing',
                'subject': [
                    {'item': u'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'original_spec_nvr': u'bodhi-2.0-1.fc17'},
                    {'item': u'FEDORA-2018-a3bbe1a8f2', 'type': 'bodhi_update'}
                ]
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        self.assertEqual(
            res.json_body,
            {
                u'errors': [
                    {
                        u'description': u'Un-expected error foo bar',
                        u'location': u'body',
                        u'name': u'request'
                    }
                ],
                u'status': u'error'}
        )

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_timing_out_on_greenwave(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument but that call raises a TimeOut error.
        """
        nvr = u'bodhi-2.0-1.fc17'
        call_api.side_effect = requests.exceptions.Timeout(
            'Request to greenwave timed out')

        res = self.app.get('/updates/%s/get-test-results' % str(nvr), status=504)

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': u'fedora-17',
                'decision_context': u'bodhi_update_push_testing',
                'subject': [
                    {'item': u'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'original_spec_nvr': u'bodhi-2.0-1.fc17'},
                    {'item': u'FEDORA-2018-a3bbe1a8f2', 'type': 'bodhi_update'}
                ]
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        self.assertEqual(
            res.json_body,
            {
                u'errors': [
                    {
                        u'description': u'Request to greenwave timed out',
                        u'location': u'body',
                        u'name': u'request'
                    }
                ],
                u'status': u'error'}
        )

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_calling_greenwave(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument.
        """
        nvr = u'bodhi-2.0-1.fc17'
        call_api.return_value = {"foo": "bar"}

        res = self.app.get('/updates/%s/get-test-results' % str(nvr))

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': u'fedora-17',
                'decision_context': u'bodhi_update_push_testing',
                'subject': [
                    {'item': u'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'original_spec_nvr': u'bodhi-2.0-1.fc17'},
                    {'item': u'FEDORA-2018-a3bbe1a8f2', 'type': 'bodhi_update'}
                ]
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        self.assertEqual(res.json_body, {u'decision': {u'foo': u'bar'}})

    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_calling_greenwave_no_session(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument.
        """
        nvr = u'bodhi-2.0-1.fc17'
        call_api.return_value = {"foo": "bar"}

        with mock.patch('bodhi.server.Session.remove'):
            app = BodhiTestApp(main(
                {}, testing=u'bodhi', session=self.db,
                greenwave_api_url='https://greenwave.api', **self.app_settings))
            res = app.get('/updates/%s/get-test-results' % str(nvr))

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': u'fedora-17',
                'decision_context': u'bodhi_update_push_testing',
                'subject': [
                    {'item': u'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'original_spec_nvr': u'bodhi-2.0-1.fc17'},
                    {'item': u'FEDORA-2018-a3bbe1a8f2', 'type': 'bodhi_update'}
                ]
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        self.assertEqual(res.json_body, {u'decision': {u'foo': u'bar'}})

    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_calling_greenwave_unauth(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument unauthenticated but the db does not know the specified update.
        """
        nvr = u'bodhi-2.0-1.fc17'
        call_api.return_value = {"foo": "bar"}

        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
            'greenwave_api_url': 'https://greenwave.api',
        })
        # with mock.patch('bodhi.server.Session.remove'):
        app = BodhiTestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/updates/%s/get-test-results' % nvr, status=404)

        self.assertEqual(
            res.json_body,
            {
                u'errors': [
                    {
                        u'description': u'Invalid update id',
                        u'location': u'url',
                        u'name': u'id'
                    }
                ],
                u'status': u'error'
            }
        )

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.call_api', wraps=call_api)
    def test_get_test_results_calling_greenwave_500(self, call_api, http_session, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument but greenwave returns a 500 error
        """
        nvr = u'bodhi-2.0-1.fc17'
        request = mock.MagicMock()
        request.status_code = 500
        http_session.post.return_value = request

        up = self.db.query(Update).filter_by(title=nvr).one()
        up.locked = False

        res = self.app.get('/updates/%s/get-test-results' % str(nvr), status=502)

        self.assertEqual(call_api.call_count, 4)
        self.assertEqual(
            res.json_body,
            {
                u'errors': [
                    {
                        u'description': u'Bodhi failed to send POST request to '
                        u'Greenwave at the following URL '
                        u'"https://greenwave.api/decision". '
                        u'The status code was "500".',
                        u'location': u'body',
                        u'name': u'request'
                    }
                ],
                'status': u'error'
            }
        )
