# Copyright 2011-2019 Red Hat, Inc. and others.
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
from html import escape
from unittest import mock
from urllib import parse as urlparse
import copy
import re
import textwrap
import time

from fedora_messaging import api
from fedora_messaging import testing as fml_testing
from webtest import TestApp
import koji
import pytest
import requests

from bodhi.messages.schemas import base as base_schemas
from bodhi.messages.schemas import update as update_schemas
from bodhi.server import main
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException, LockedUpdateException
from bodhi.server.models import (
    Build,
    BuildrootOverride,
    Compose,
    Group,
    ModulePackage,
    PackageManager,
    Release,
    ReleaseState,
    RpmBuild,
    RpmPackage,
    TestGatingStatus,
    Update,
    UpdateRequest,
    UpdateSeverity,
    UpdateStatus,
    UpdateSuggestion,
    UpdateType,
    User,
)
from bodhi.server.util import call_api

from ..base import BasePyTestCase
from ..utils import assert_multiline_equal


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


def unused_mock_patch(_mockcls=mock.MagicMock, **kwargs):
    target = kwargs.pop('target')
    mockobj = _mockcls(**kwargs)
    return mock.patch(target, new=mockobj)


@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestNewUpdate(BasePyTestCase):
    """
    This class contains tests for the new_update() function.
    """

    @classmethod
    def mock_getTag(cls, tag, *kwargs):
        if tag == 'f17-build-side-7777':
            return {'maven_support': False, 'locked': False, 'name': 'f17-build-side-7777',
                    'extra': {'sidetag_user': 'guest', 'sidetag': True},
                    'perm': None, 'perm_id': None, 'arches': None, 'maven_include_all': False,
                    'id': 7777}
        return None

    @mock.patch(**mock_valid_requirements)
    def test_empty_build_name(self, *args):
        res = self.app.post_json('/updates/', self.get_update(['']), status=400)
        assert res.json_body['errors'][0]['name'] == 'builds.0'
        assert res.json_body['errors'][0]['description'] == 'Required'

    @mock.patch(**mock_valid_requirements)
    def test_fail_on_edit_with_empty_build_list(self, *args):
        update = self.get_update()
        update['edited'] = update['builds']  # the update title..
        update['builds'] = []
        res = self.app.post_json('/updates/', update, status=400)
        errors = res.json_body['errors']
        assert len(errors) == 3
        assert {'location': 'body', 'name': 'builds',
                'description': f"Cannot find update to edit: {update['edited']}"} in errors
        assert {'location': 'body', 'name': 'builds',
                'description': 'You may not specify an empty list of builds.'} in errors
        assert {'location': 'body', 'name': 'builds',
                'description': 'ACL validation mechanism was unable to determine ACLs.'} in errors

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_unicode_description(self, *args):
        # We don't want the new update to obsolete the existing one.
        self.db.delete(Update.query.one())
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['notes'] = 'This is wünderfül'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', update)

        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-2.fc17'
        assert up['notes'] == 'This is wünderfül'
        assert up['date_submitted'] is not None

    @mock.patch(**mock_valid_requirements)
    def test_duplicate_build(self, *args):
        res = self.app.post_json(
            '/updates/', self.get_update(['bodhi-2.0-2.fc17', 'bodhi-2.0-2.fc17']), status=400)
        assert 'Duplicate builds' in res

    @mock.patch(**mock_valid_requirements)
    def test_multiple_builds_of_same_package(self, *args):
        res = self.app.post_json('/updates/', self.get_update(['bodhi-2.0-2.fc17',
                                                               'bodhi-2.0-3.fc17']),
                                 status=400)
        assert 'Multiple bodhi builds specified' in res

    @mock.patch(**mock_valid_requirements)
    def test_invalid_autokarma(self, *args):
        res = self.app.post_json('/updates/', self.get_update(stable_karma=-1),
                                 status=400)
        assert '-1 is less than minimum value 1' in res
        res = self.app.post_json('/updates/', self.get_update(unstable_karma=1),
                                 status=400)
        assert '1 is greater than maximum value -1' in res

    @mock.patch(**mock_valid_requirements)
    def test_duplicate_update(self, *args):
        res = self.app.post_json('/updates/', self.get_update('bodhi-2.0-1.fc17'),
                                 status=400)
        assert 'Update for bodhi-2.0-1.fc17 already exists' in res

    @mock.patch(**mock_valid_requirements)
    def test_unpushed_update(self, *args):
        """Allow posting a duplicate build if the old update is unpushed."""
        unpushed_update = self.create_update(['whoopsie-1.0.0-1.fc17'])
        unpushed_update.status = UpdateStatus.unpushed
        self.db.commit()

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = self.app.post_json('/updates/', self.get_update('whoopsie-1.0.0-1.fc17'))

        assert res.json['alias'] != unpushed_update.alias

    @mock.patch(**mock_valid_requirements)
    def test_invalid_requirements(self, *args):
        update = self.get_update()
        update['requirements'] = 'rpmlint silly-dilly'
        res = self.app.post_json('/updates/', update, status=400)
        assert "Required check doesn't exist" in res

    @mock.patch(**mock_valid_requirements)
    def test_no_privs(self, *args):
        user = User(name='bodhi')
        self.db.add(user)
        self.db.commit()
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='bodhi', session=self.db, **self.app_settings))
        update_json = self.get_update('bodhi-2.1-1.fc17')
        update_json['csrf_token'] = self.get_csrf_token(app)

        with fml_testing.mock_sends():
            res = app.post_json('/updates/', update_json, status=400)

        expected_error = {
            "location": "body",
            "name": "builds",
            "description": ("bodhi is not a member of \"packager\", which is a"
                            " mandatory packager group")
        }
        assert expected_error in res.json_body['errors']

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_privs(self, *args):
        "Ensure provenpackagers can push updates for any package"
        user = User(name='bodhi')
        self.db.add(user)
        self.db.commit()
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)

        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='bodhi', session=self.db, **self.app_settings))
        update = self.get_update('bodhi-2.1-1.fc17')
        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = app.post_json('/updates/', update)

        assert 'bodhi does not have commit access to bodhi' not in res
        build = self.db.query(RpmBuild).filter_by(nvr='bodhi-2.1-1.fc17').one()
        assert build.update is not None

    @mock.patch(**mock_valid_requirements)
    def test_invalid_acl_system(self, *args):
        with mock.patch.dict(config, {'acl_system': 'null'}):
            res = self.app.post_json('/updates/', self.get_update('bodhi-2.0-2.fc17'),
                                     status=403)

        assert "guest does not have commit access to bodhi" in res

    def test_put_json_update(self):
        self.app.put_json('/updates/', self.get_update(), status=405)

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_post_json_update(self, *args):
        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-1.fc17'))

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_new_rpm_update(self, *args):
        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'))

        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-2.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'rpm'
        assert up['severity'] == 'unspecified'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        # The notes are inheriting notes from the update that this update obsoleted.
        assert up['notes'] == 'this is a test update\n\n----\n\nUseful details!'
        assert up['date_submitted'] is not None
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-033713b73b'
        assert up['karma'] == 0
        assert up['requirements'] == 'rpmlint'

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_new_rawhide_rpm_update(self, *args):
        """Posting a new update against Rawhide should fail."""
        release = Release.query.one()
        release.composed_by_bodhi = False
        self.db.commit()
        with fml_testing.mock_sends():
            res = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'),
                                     status=400)

        expected_error = {
            "location": "body",
            "name": "builds",
            "description": ("Cannot manually create updates for a Release which is not "
                            "composed by Bodhi.\nRead the 'Automatic updates' page in "
                            "Bodhi docs about this error.")
        }
        assert expected_error in res.json_body['errors']
        build = self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first()
        assert build is None

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_new_rpm_update_unknown_build(self, *args):
        with mock.patch('bodhi.server.buildsys.DevBuildsys.getBuild',
                        return_value=None):
            r = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'),
                                   status=400)
            up = r.json_body

        assert up['status'] == 'error'
        assert up['errors'][0]['description'] == "Build does not exist: bodhi-2.0.0-2.fc17"

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_new_rpm_update_koji_error(self, *args):
        with mock.patch('bodhi.server.buildsys.DevBuildsys.getBuild',
                        side_effect=koji.GenericError()):
            r = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'),
                                   status=400)
            up = r.json_body

        assert up['status'] == 'error'
        assert up['errors'][0]['description'] == "Koji error getting build: bodhi-2.0.0-2.fc17"

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task')
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @unused_mock_patch(**mock_uuid4_version1)
    @unused_mock_patch(**mock_valid_requirements)
    @pytest.mark.parametrize('rawhide_workflow', (True, False))
    def test_new_rpm_update_from_tag(self, handle_side_and_related_tags_task, rawhide_workflow):
        """Test creating an update using builds from a Koji tag."""
        # We don't want the new update to obsolete the existing one.
        self.db.delete(Update.query.one())

        if rawhide_workflow:
            # We need a release that isn't composed by bodhi
            release = Release.query.one()
            release.composed_by_bodhi = False
            self.db.commit()

        update = self.get_update(builds=None, from_tag='f17-build-side-7777')
        # Let's test what happens if the user sets autotime to False
        # Rawhide workflow must ignore this setting
        update['autotime'] = False
        update['stable_days'] = 7
        with mock.patch('bodhi.server.buildsys.DevBuildsys.getTag', self.mock_getTag):
            with mock.patch('bodhi.server.models.Release.mandatory_days_in_testing', 0):
                r = self.app.post_json('/updates/', update)

        up = r.json_body
        assert up['title'] == 'gnome-backgrounds-3.0-1.fc17'
        assert up['builds'][0]['nvr'] == 'gnome-backgrounds-3.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] is None
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'rpm'
        assert up['severity'] == 'unspecified'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'this is a test update'
        assert up['date_submitted'] is not None
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] in (f'FEDORA-{YEAR}-033713b73b', f'FEDORA-{YEAR + 1}-033713b73b')
        assert up['karma'] == 0
        assert up['requirements'] == 'rpmlint'
        assert up['from_tag'] == 'f17-build-side-7777'
        if rawhide_workflow:
            assert up['autotime'] is True
            assert up['stable_days'] == 0
        else:
            assert up['autotime'] is False
            assert up['stable_days'] == 7

        resp = self.app.get(f"/updates/{up['alias']}", headers={'Accept': 'text/html'})

        handle_side_and_related_tags_task.delay.assert_called_once()
        called_args = handle_side_and_related_tags_task.delay.call_args[1]
        # don't check the first argument, it's the update object
        assert called_args['builds'] == ['gnome-backgrounds-3.0-1.fc17']
        assert called_args['from_tag'] == 'f17-build-side-7777'

        if rawhide_workflow:
            # check that the sidetag gets displayed on the update page
            assert 'title="Builds from the Side Tag: f17-build-side-7777' in resp
            assert called_args['pending_signing_tag'] == 'f17-build-side-7777-signing-pending'
            assert called_args['pending_testing_tag'] == 'f17-build-side-7777-testing-pending'
        else:
            # the sidetag should be still displayed on the update page
            assert 'title="Builds from the Side Tag: f17-build-side-7777' in resp
            assert called_args['pending_signing_tag'] == 'f17-updates-signing-pending'

        # now try to create another update with the same side tag
        update = self.get_update(builds=None, from_tag='f17-build-side-7777')
        with fml_testing.mock_sends(), mock.patch(
                'bodhi.server.buildsys.DevBuildsys.getTag', self.mock_getTag):
            r = self.app.post_json('/updates/', update, status=400)

        assert r.json_body['errors'][0]['description'] == (
            "Update already exists using this side tag"
        )

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task')
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @unused_mock_patch(**mock_uuid4_version1)
    @unused_mock_patch(**mock_valid_requirements)
    @pytest.mark.parametrize('rawhide_workflow', (True, False))
    def test_new_rpm_update_from_tag_wrong_owner(self, handle_side_and_related_tags_task,
                                                 rawhide_workflow):
        """
        Test creating an update using builds from a Koji tag fails if user doesn't own
        the side-tag.
        """
        # We don't want the new update to obsolete the existing one.
        self.db.delete(Update.query.one())

        if rawhide_workflow:
            # We need a release that isn't composed by bodhi
            release = Release.query.one()
            release.composed_by_bodhi = False
            self.db.commit()

        update = self.get_update(builds=None, from_tag='f17-build-side-7777')

        user = User(name='mattia')
        self.db.add(user)
        self.db.commit()
        group = self.db.query(Group).filter_by(name='packager').one()
        user.groups.append(group)

        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='mattia', session=self.db, **self.app_settings))

        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']

        with mock.patch('bodhi.server.buildsys.DevBuildsys.getTag', self.mock_getTag):
            with mock.patch('bodhi.server.models.Release.mandatory_days_in_testing', 0):
                r = app.post_json('/updates/', update, status=403)
        assert r.json_body['errors'][0]['description'] == (
            "mattia does not own f17-build-side-7777 side-tag"
        )

    @mock.patch(**mock_valid_requirements)
    def test_koji_config_url(self, *args):
        """
        Test html rendering of default build link
        """
        self.registry.settings['koji_web_url'] = \
            'https://koji.fedoraproject.org/koji/'
        nvr = 'bodhi-2.0.0-2.fc17'
        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', self.get_update(nvr))

        resp = self.app.get(f"/updates/{resp.json['alias']}", headers={'Accept': 'text/html'})

        assert re.search(r'https://koji.fedoraproject.org/koji/search\?terms=.*\&amp;'
                         r'type=build\&amp;match=exact', str(resp))

    @mock.patch(**mock_valid_requirements)
    def test_koji_config_url_without_trailing_slash(self, *args):
        """
        Test html rendering of default build link without trailing slash
        """
        self.registry.settings['koji_web_url'] = \
            'https://koji.fedoraproject.org/koji'
        nvr = 'bodhi-2.0.0-2.fc17'
        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', self.get_update(nvr))

        resp = self.app.get(f"/updates/{resp.json['alias']}", headers={'Accept': 'text/html'})

        assert re.search(r'https://koji.fedoraproject.org/koji/search\?terms=.*\&amp;'
                         r'type=build\&amp;match=exact', str(resp))

    @mock.patch(**mock_valid_requirements)
    def test_koji_config_mock_url_without_trailing_slash(self, *args):
        """
        Test html rendering of build link using a mock config variable 'koji_web_url'
        without a trailing slash in it
        """
        self.registry.settings['koji_web_url'] = 'https://host.org'
        nvr = 'bodhi-2.0.0-2.fc17'
        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', self.get_update(nvr))

        resp = self.app.get(f"/updates/{resp.json['alias']}", headers={'Accept': 'text/html'})

        assert re.search(r'https://host.org/search\?terms=.*\&amp;type=build\&amp;match=exact',
                         str(resp))

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_new_module_update(self, *args):
        # Ensure there are no module packages in the DB to begin with.
        assert not self.db.query(ModulePackage).count()
        self.create_release('27M')
        # Then, create an update for one.
        data = self.get_update('nginx-master-20170523')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', data)

        up = r.json_body
        assert up['title'] == 'nginx-master-20170523'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F27M'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'module'
        assert up['severity'] == 'unspecified'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'this is a test update'
        assert up['date_submitted'] is not None
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-033713b73b'
        assert up['karma'] == 0
        assert up['requirements'] == 'rpmlint'
        # At the end, ensure that the right kind of package was created.
        assert self.db.query(ModulePackage).count() == 1

    @mock.patch(**mock_valid_requirements)
    def test_multiple_builds_of_same_module_stream(self, *args):
        self.create_release('27M')

        res = self.app.post_json('/updates/', self.get_update(['nodejs-6-20170101',
                                                               'nodejs-6-20170202']),
                                 status=400)
        assert 'Multiple nodejs:6 builds specified' in res

    @mock.patch(**mock_valid_requirements)
    def test_multiple_builds_of_different_module_stream(self, *args):
        self.create_release('27M')

        with fml_testing.mock_sends(api.Message):
            res = self.app.post_json('/updates/', self.get_update(['nodejs-6-20170101',
                                                                   'nodejs-8-20170202']))
        res = res.json
        assert res['request'] == 'testing'
        assert len(res['builds']) == 2
        assert res['builds'][0]['type'] == 'module'
        assert res['builds'][1]['type'] == 'module'
        assert res['builds'][0]['nvr'] == 'nodejs-6-20170101'
        assert res['builds'][1]['nvr'] == 'nodejs-8-20170202'
        assert res['title'] == 'nodejs-6-20170101 nodejs-8-20170202'

        # At the end, ensure that the right kind of packages were created.
        assert self.db.query(ModulePackage).count() == 2

    @mock.patch(**mock_valid_requirements)
    def test_multiple_updates_single_module_stream(self, *args):
        # Ensure there are no module packages in the DB to begin with.
        assert not self.db.query(ModulePackage).count()
        self.create_release('27M')

        # First create an update for nodejs:6
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/updates/', self.get_update('nodejs-6-20170101'))

        # Next create a second update for nodejs:6
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/updates/', self.get_update('nodejs-6-20170202'))

        # At the end, ensure that the right kind of package was created.
        assert self.db.query(ModulePackage).count() == 1
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
    def test_new_container_update(self, *args):
        self.create_release('28C')
        data = self.get_update('mariadb-10.1-10.f28container')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', data, status=200)

        up = r.json_body
        assert up['title'] == 'mariadb-10.1-10.f28container'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F28C'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'container'
        assert up['severity'] == 'unspecified'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'this is a test update'
        assert up['date_submitted'] is not None
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-033713b73b'
        assert up['karma'] == 0
        assert up['requirements'] == 'rpmlint'

    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_new_flatpak_update(self, *args):
        self.create_release('28F')
        data = self.get_update('mariadb-10.1-10.f28flatpak')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', data, status=200)

        up = r.json_body
        assert up['title'] == 'mariadb-10.1-10.f28flatpak'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F28F'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'flatpak'
        assert up['severity'] == 'unspecified'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'this is a test update'
        assert up['date_submitted'] is not None
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-033713b73b'
        assert up['karma'] == 0
        assert up['requirements'] == 'rpmlint'

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_multiple_bugs(self, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = ['1234', '5678']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', update)

        up = r.json_body
        # This Update inherits one bug from the Update it obsoleted.
        assert len(up['bugs']) == 3
        assert up['bugs'][0]['bug_id'] == 1234
        assert up['bugs'][1]['bug_id'] == 5678
        assert up['bugs'][2]['bug_id'] == 12345

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_update_with_high_stable_days(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['stable_days'] = 10
        r = self.app.post_json('/updates/', update)
        up = r.json_body

        assert up['stable_days'] == 10

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_new_update_with_invalid_stable_days(self, publish, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['stable_days'] = -1
        r = self.app.post_json('/updates/', update, status=400)
        up = r.json_body

        assert up['status'] == 'error'
        assert up['errors'][0]['description'] == "-1 is less than minimum value 0"

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_update_stable_days(self, publish, *args):
        args = self.get_update(u'bodhi-2.0.0-2.fc17')
        args['stable_days'] = '50'
        r = self.app.post_json('/updates/', args)
        assert r.json['stable_days'] == 50

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.notifications.publish')
    def test_edit_update_too_low_stable_days(self, publish, *args):
        args = self.get_update(u'bodhi-2.0.0-2.fc17')
        args['stable_days'] = '1'
        r = self.app.post_json('/updates/', args)
        assert r.json['stable_days'] == 7
        assert r.json['caveats'][0]['description'] == (
            'The number of stable days required was set to the mandatory release value of 7 days'
        )

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': u'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_multiple_bugs_as_str(self, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = '1234, 5678'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', update)

        up = r.json_body
        # This Update inherits one bug from the Update it obsoleted.
        assert len(up['bugs']) == 3
        assert up['bugs'][0]['bug_id'] == 1234
        assert up['bugs'][1]['bug_id'] == 5678
        assert up['bugs'][2]['bug_id'] == 12345

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_invalid_bugs_as_str(self, *args):
        update = self.get_update('bodhi-2.0.0-2.fc17')
        update['bugs'] = '1234, blargh'
        r = self.app.post_json('/updates/', update, status=400)
        up = r.json_body
        assert up['status'] == 'error'
        assert up['errors'][0]['description'] == (
            "Invalid bug ID specified: {}".format(['1234', 'blargh'])
        )

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_existing_build(self, *args):
        """Test submitting a new update with a build already in the database"""
        package = RpmPackage.get('bodhi')
        self.db.add(RpmBuild(nvr='bodhi-2.0.0-3.fc17', package=package))
        self.db.commit()

        args = self.get_update('bodhi-2.0.0-3.fc17')
        with fml_testing.mock_sends(api.Message):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['title'] == 'bodhi-2.0.0-3.fc17'

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_existing_package(self, *args):
        """Test submitting a new update with a package that is already in the database."""
        package = RpmPackage(name='existing-package')
        self.db.add(package)
        self.db.commit()
        args = self.get_update('existing-package-2.4.1-5.fc17')

        with fml_testing.mock_sends(api.Message):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['title'] == 'existing-package-2.4.1-5.fc17'
        package = self.db.query(RpmPackage).filter_by(name='existing-package').one()
        assert package.name == 'existing-package'

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    @mock.patch(**mock_valid_requirements)
    def test_new_update_with_missing_package(self, *args):
        """Test submitting a new update with a package that is not already in the database."""
        args = self.get_update('missing-package-2.4.1-5.fc17')

        with fml_testing.mock_sends(api.Message):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['title'] == 'missing-package-2.4.1-5.fc17'
        package = self.db.query(RpmPackage).filter_by(name='missing-package').one()
        assert package.name == 'missing-package'

    @mock.patch(**mock_valid_requirements)
    def test_cascade_package_requirements_to_update(self, *args):

        package = self.db.query(RpmPackage).filter_by(name='bodhi').one()
        package.requirements = 'upgradepath rpmlint'
        self.db.commit()

        args = self.get_update('bodhi-2.0.0-3.fc17')
        # Don't specify any requirements so that they cascade from the package
        del args['requirements']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert 'upgradepath' in up['requirements']
        assert 'rpmlint' in up['requirements']

    @mock.patch(**mock_valid_requirements)
    def test_push_untested_critpath_to_release(self, *args):
        """
        Ensure that we cannot push an untested critpath update directly to
        stable.
        """
        args = self.get_update('kernel-3.11.5-300.fc17')
        args['request'] = 'stable'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            up = self.app.post_json('/updates/', args).json_body

        assert up['critpath']
        assert up['request'] == 'testing'

    @mock.patch(**mock_valid_requirements)
    def test_obsoletion(self, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with mock.patch(**mock_uuid4_version1):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.testing
        up.request = None
        # Clear pending messages
        self.db.info['messages'] = []

        args = self.get_update('bodhi-2.0.0-3.fc17')
        with mock.patch(**mock_uuid4_version2):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                r = self.app.post_json('/updates/', args).json_body
        assert r['request'] == 'testing'

        # Since we're obsoleting something owned by someone else.
        assert r['caveats'][1]['description'] == ('This update has obsoleted bodhi-2.0.0-2.fc17, '
                                                  'and has inherited its bugs and notes.')

        # Check for the comment multiple ways
        # Note that caveats above don't support markdown, but comments do.
        expected_comment = (
            'This update has obsoleted [bodhi-2.0.0-2.fc17]({}), '
            'and has inherited its bugs and notes.')
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-033713b73b'.format(datetime.now().year)))
        assert r['comments'][-1]['text'] == expected_comment
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.obsolete
        expected_comment = 'This update has been obsoleted by [bodhi-2.0.0-3.fc17]({}).'
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-53345602d5'.format(datetime.now().year)))
        assert up.comments[-1].text == expected_comment

    @mock.patch(**mock_valid_requirements)
    def test_create_new_nonsecurity_update_when_previous_security_one_exists(self, *args):
        """
        Assert that when non-security update obsoletes previous security update, caveat is reported
        and submitted update type is changed to security.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args["type"] = "security"
        args["severity"] = "high"
        with mock.patch(**mock_uuid4_version1):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.testing
        up.request = None
        # Clear pending messages
        self.db.info['messages'] = []

        args = self.get_update('bodhi-2.0.0-3.fc17')
        with mock.patch(**mock_uuid4_version2):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                r = self.app.post_json('/updates/', args).json_body

        # Since we're trying to obsolete security update with non security update.
        assert r['caveats'][1]['description'] == ('Adjusting type of this update to security,'
                                                  'since it obsoletes another security update')
        assert r['request'] == 'testing'

        # Since we're obsoleting something owned by someone else.
        assert r['caveats'][2]['description'] == ('This update has obsoleted bodhi-2.0.0-2.fc17, '
                                                  'and has inherited its bugs and notes.')

        # Check for the comment multiple ways
        # Note that caveats above don't support markdown, but comments do.
        expected_comment = (
            'This update has obsoleted [bodhi-2.0.0-2.fc17]({}), '
            'and has inherited its bugs and notes.')
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-033713b73b'.format(datetime.now().year)))
        assert r['comments'][-1]['text'] == expected_comment
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.obsolete
        expected_comment = 'This update has been obsoleted by [bodhi-2.0.0-3.fc17]({}).'
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-53345602d5'.format(datetime.now().year)))
        assert up.comments[-1].text == expected_comment

        # Assert that the type of the new update is security.
        up = self.db.query(Build).filter_by(nvr='bodhi-2.0.0-3.fc17').one().update
        assert up.type == UpdateType.security
        assert up.severity == UpdateSeverity.high

    @mock.patch(**mock_valid_requirements)
    def test_obsoletion_security_update(self, *args):
        """Assert that security update can obsolete previous security update."""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args["type"] = "security"
        args["severity"] = "high"
        with mock.patch(**mock_uuid4_version1):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.testing
        up.request = None
        # Clear pending messages
        self.db.info['messages'] = []

        args = self.get_update('bodhi-2.0.0-3.fc17')
        args["type"] = "security"
        args["severity"] = "high"
        with mock.patch(**mock_uuid4_version2):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                r = self.app.post_json('/updates/', args).json_body

        assert r['request'] == 'testing'

        # Since we're obsoleting something owned by someone else.
        assert r['caveats'][1]['description'] == ('This update has obsoleted bodhi-2.0.0-2.fc17, '
                                                  'and has inherited its bugs and notes.')

        # Check for the comment multiple ways
        # Note that caveats above don't support markdown, but comments do.
        expected_comment = (
            'This update has obsoleted [bodhi-2.0.0-2.fc17]({}), '
            'and has inherited its bugs and notes.')
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-033713b73b'.format(datetime.now().year)))
        assert r['comments'][-1]['text'] == expected_comment
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.obsolete
        expected_comment = 'This update has been obsoleted by [bodhi-2.0.0-3.fc17]({}).'
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-53345602d5'.format(datetime.now().year)))
        assert up.comments[-1].text == expected_comment

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.services.updates.Update.new', side_effect=IOError('oops!'))
    def test_unexpected_exception(self, *args):
        """Ensure that an unexpected Exception is handled by new_update()."""
        update = self.get_update('bodhi-2.3.2-1.fc17')

        r = self.app.post_json('/updates/', update, status=400)

        assert r.json_body['status'] == 'error'
        assert r.json_body['errors'][0]['description'] == "Unable to create update.  oops!"
        # Despite the Exception, the RpmBuild should still exist in the database
        build = self.db.query(RpmBuild).filter(RpmBuild.nvr == 'bodhi-2.3.2-1.fc17').one()
        assert build.package.name == 'bodhi'

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.services.updates.Update.obsolete_older_updates',
                side_effect=RuntimeError("bet you didn't see this coming!"))
    def test_obsoletion_with_exception(self, *args):
        """
        Assert that an exception during obsoletion is properly handled.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with mock.patch(**mock_uuid4_version1):
            with fml_testing.mock_sends(api.Message):
                self.app.post_json('/updates/', args)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.testing
        up.request = None
        # Clear pending messages
        self.db.info['messages'] = []
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with mock.patch(**mock_uuid4_version2):
            with fml_testing.mock_sends(api.Message):
                r = self.app.post_json('/updates/', args).json_body

        assert r['request'] == 'testing'
        # The exception handler should have put an error message in the caveats.
        assert r['caveats'][1]['description'] == (
            "Problem obsoleting older updates: bet you didn't see this coming!"
        )
        # Check for the comment multiple ways. The comment will be about the update being submitted
        # for testing instead of being about the obsoletion, since the obsoletion failed.
        # Note that caveats above don't support markdown, but comments do.
        expected_comment = 'This update has been submitted for testing by guest. '
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'], '/updates/FEDORA-2016-033713b73b'))
        assert r['comments'][-1]['text'] == expected_comment
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The old update failed to get obsoleted.
        assert up.status == UpdateStatus.testing
        expected_comment = 'This update has been submitted for testing by guest. '
        assert up.comments[-1].text == expected_comment

    @mock.patch(**mock_valid_requirements)
    def test_security_update_without_severity(self, *args):
        """Ensure that severity is required for a security update."""
        update = self.get_update('bodhi-2.3.2-1.fc17')
        update['type'] = 'security'
        update['severity'] = 'unspecified'

        r = self.app.post_json('/updates/', update, status=400)

        assert r.json_body['status'] == 'error'
        assert r.json_body['errors'][0]['description'] == (
            "Must specify severity for a security update"
        )


class TestSetRequest(BasePyTestCase):
    """
    This class contains tests for the set_request() function.
    """
    @mock.patch(**mock_valid_requirements)
    def test_set_request_locked_update(self, *args):
        """Ensure that we get an error if trying to set request of a locked update"""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = True

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json(f'/updates/{up.alias}/request', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            "Can't change request on a locked update"
        )

    @mock.patch(**mock_valid_requirements)
    def test_set_request_archived_release(self, *args):
        """Ensure that we get an error if trying to setrequest of a update in an archived release"""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False
        up.release.state = ReleaseState.archived

        post_data = dict(update=up.alias, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f'/updates/{up.alias}/request', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            "cannot edit Update for an archived Release"
        )

    @mock.patch(**mock_valid_requirements)
    def test_set_request_testing_from_stable(self, *args):
        """Ensure that we get an error if trying to push to testing a stable update"""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False
        up.status = UpdateStatus.stable

        post_data = dict(update=up.alias, request='testing',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f'/updates/{up.alias}/request', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            "Pushing back to testing a stable update is not allowed"
        )

    @mock.patch('bodhi.server.services.updates.log.info')
    @mock.patch.dict(config, {'test_gating.required': True})
    def test_test_gating_status_failed(self, info):
        """If the update's test_gating_status is failed, a user should not be able to push."""
        nvr = 'bodhi-2.0-1.fc17'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False
        up.requirements = ''
        up.test_gating_status = TestGatingStatus.failed
        up.date_testing = datetime.utcnow() - timedelta(days=8)
        up.request = None
        post_data = dict(update=nvr, request='stable', csrf_token=self.get_csrf_token())

        res = self.app.post_json(f'/updates/{up.alias}/request', post_data, status=400)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.request is None
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            "Requirement not met Required tests did not pass on this update"
        )
        info_logs = '\n'.join([c[1][0] for c in info.mock_calls])
        assert (f'Unable to set request for {up.alias} to stable due to failed requirements: '
                'Required tests did not pass on this update') in info_logs

    @mock.patch.dict(config, {'test_gating.required': True})
    def test_test_gating_status_passed(self):
        """If the update's test_gating_status is passed, a user should be able to push."""
        nvr = 'bodhi-2.0-1.fc17'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False
        up.requirements = ''
        up.test_gating_status = TestGatingStatus.passed
        up.date_testing = datetime.utcnow() - timedelta(days=8)
        post_data = dict(update=nvr, request='stable', csrf_token=self.get_csrf_token())

        with fml_testing.mock_sends(api.Message):
            res = self.app.post_json(f'/updates/{up.alias}/request', post_data, status=200)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.request == UpdateRequest.stable
        assert res.json['update']['request'] == 'stable'

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.services.updates.Update.set_request',
                side_effect=BodhiException('BodhiException. oops!'))
    @mock.patch('bodhi.server.services.updates.Update.check_requirements',
                return_value=(True, "a fake reason"))
    @mock.patch('bodhi.server.services.updates.log.info')
    def test_BodhiException_exception(self, log_info, check_requirements, send_request, *args):
        """Ensure that an BodhiException Exception is handled by set_request()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False
        up.release.state = ReleaseState.current

        post_data = dict(update=up.alias, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f"/updates/{post_data['update']}/request", post_data,
                                 status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'BodhiException. oops!'
        assert log_info.call_count == 1
        assert log_info.call_args_list[0][0][0] == "Failed to set the request: %s"

    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.services.updates.Update.set_request',
                side_effect=IOError('IOError. oops!'))
    @mock.patch('bodhi.server.services.updates.Update.check_requirements',
                return_value=(True, "a fake reason"))
    @mock.patch('bodhi.server.services.updates.log.exception')
    def test_unexpected_exception(self, log_exception, check_requirements, send_request, *args):
        """Ensure that an unexpected Exception is handled by set_request()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False
        up.release.state = ReleaseState.current

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        res = self.app.post_json(f'/updates/{up.alias}/request', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'IOError. oops!'
        log_exception.assert_called_once_with("Unhandled exception in set_request")


@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestEditUpdateForm(BasePyTestCase):

    def test_edit_with_permission(self):
        """
        Test a logged in User with permissions on the update can see the form
        """
        resp = self.app.get(
            '/updates/FEDORA-{}-a3bbe1a8f2/edit'.format(datetime.utcnow().year),
            headers={'accept': 'text/html'})
        assert 'Editing an update requires JavaScript' in resp
        # Make sure that unspecified comes first, as it should be the default.
        regex = '<select id="suggest" name="suggest">\\n.*<option value="unspecified"'
        assert re.search(regex, str(resp))

    def test_edit_without_permission(self):
        """
        Test a logged in User without permissions on the update can't see the form
        """
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='anonymous', session=self.db, **self.app_settings))

        resp = app.get(
            '/updates/FEDORA-{}-a3bbe1a8f2/edit'.format(datetime.utcnow().year), status=400,
            headers={'accept': 'text/html'})
        assert (
            'anonymous is not a member of &#34;packager&#34;, which is a mandatory packager group'
        ) in resp

    def test_edit_not_loggedin(self):
        """
        Test a non logged in User can't see the form
        """
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = TestApp(main({}, session=self.db, **anonymous_settings))
        resp = app.get('/updates/FEDORA-2017-a3bbe1a8f2/edit', status=403,
                       headers={'accept': 'text/html'})
        assert '<h1>403 <small>Forbidden</small></h1>' in resp
        assert (
            '<p class="lead">Unauthorized: get_update_for_editing__GET failed permission check</p>'
            in resp
        )

    def test_disabled_unspecified_severity_for_security_update(self):
        alias = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update.alias
        update_json = self.get_update()
        update_json['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        update_json['edited'] = alias
        update_json['requirements'] = ''
        update_json['type'] = 'security'
        update_json['severity'] = 'low'
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/updates/', update_json)

        resp = self.app.get(f'/updates/{alias}/edit',
                            headers={'accept': 'text/html'})
        assert re.search(r'<select id="severity" name="severity">\n.*'
                         r'<option value="unspecified"\n.*disabled="disabled"\n.*>',
                         str(resp))

    def test_days_in_testing_new_update(self):
        """
        When creating an update the minimum value of days in testing should be set to 1
        and the value should be empty.
        """
        resp = self.app.get('/updates/new',
                            headers={'accept': 'text/html'})
        assert re.search(r'<input type="number" name="stable_days" placeholder="auto"'
                         r' class="form-control"\n.*min="0" value=""\n.*>',
                         str(resp))

    def test_days_in_testing_existing_update(self):
        """
        When editing an update the minimum value of days in testing should be set to
        the mandatory days in testing of the release and the value to the actual value
        set in the update.
        """
        alias = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update.alias
        update_json = self.get_update()
        update_json['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']
        update_json['edited'] = alias
        update_json['requirements'] = ''
        update_json['mandatory_days_in_testing'] = 7
        update_json['stable_days'] = 10
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/updates/', update_json)

        resp = self.app.get(f'/updates/{alias}/edit',
                            headers={'accept': 'text/html'})
        assert re.search(r'<input type="number" name="stable_days" placeholder="auto"'
                         r' class="form-control"\n.*min="7" value="10"\n.*>',
                         str(resp))

    def test_xss(self):
        """
        Make sure user input is sanitized.
        """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.display_name = "<script>thisIsBad()</script>"
        update.requirements = "<script>thisIsBad()</script>"
        self.db.commit()
        resp = self.app.get(f'/updates/{update.alias}/edit',
                            headers={'accept': 'text/html'})
        assert "<script>thisIsBad()</script>" not in str(resp)
        assert str(resp).count("&lt;script&gt;thisIsBad()&lt;/script&gt;") == 2


@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestUpdatesService(BasePyTestCase):
    @pytest.fixture
    def create_quick_filters_data(self):
        self.create_release('20')
        self.create_release('40')
        Release.query.filter_by(version='20').first().state = ReleaseState.archived
        Release.query.filter_by(version='40').first().state = ReleaseState.pending
        self.create_update([('really_old-1.2.3-1.fc20')], 'F20')
        self.create_update([('shiny_new-7.8.9-1.fc40')], 'F40')
        self.db.commit()

    @classmethod
    def mock_getTag(cls, tag, *kwargs):
        if tag == 'f17-build-side-7777':
            return {'maven_support': False, 'locked': False, 'name': 'f17-build-side-7777',
                    'extra': {'sidetag_user': 'guest', 'sidetag': True},
                    'perm': None, 'perm_id': None, 'arches': None, 'maven_include_all': False,
                    'id': 7777}
        return None

    def test_content_type(self):
        """Assert that the content type is displayed in the update template."""
        alias = Update.query.one().alias

        res = self.app.get(f'/updates/{alias}', status=200, headers={'Accept': 'text/html'})

        assert '<div class="col font-weight-bold text-muted">Content Type</div>' in res.text
        assert 'RPM' in res.text

    def test_content_type_none(self):
        """Assert that the content type being None doesn't blow up the update template."""
        u = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        u.builds = []
        self.db.commit()

        res = self.app.get(f'/updates/{u.alias}', status=200, headers={'Accept': 'text/html'})

        assert 'RPM' not in res.text

    def test_decision_context_pending_stable(self):
        """The HTML should include the correct decision context for Pending/Stable updates."""
        u = Update.query.one()
        u.request = UpdateRequest.stable
        u.status = UpdateStatus.pending

        res = self.app.get(f'/updates/{u.alias}', status=200, headers={'Accept': 'text/html'})

        assert '"decision_context": "bodhi_update_push_testing",' not in res
        assert '"decision_context": "bodhi_update_push_stable",' in res

    def test_decision_context_pending_testing(self):
        """The HTML should include the correct decision context for Pending/Testing updates."""
        u = Update.query.one()
        u.request = UpdateRequest.testing
        u.status = UpdateStatus.pending

        res = self.app.get(f'/updates/{u.alias}', status=200, headers={'Accept': 'text/html'})

        assert '"decision_context": "bodhi_update_push_stable",' not in res
        assert '"decision_context": "bodhi_update_push_testing",' in res

    def test_decision_context_testing(self):
        """The HTML should include the correct decision context for Testing updates."""
        u = Update.query.one()
        u.request = None
        u.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        res = self.app.get(f'/updates/{u.alias}', status=200, headers={'Accept': 'text/html'})

        assert '"decision_context": "bodhi_update_push_testing",' not in res
        assert '"decision_context": "bodhi_update_push_stable",' in res

    def test_home_html_legal(self):
        """Test the home page HTML when a legal link is configured."""
        with mock.patch.dict(
                self.registry.settings,
                {'legal_link': 'http://loweringthebar.net/'}):
            resp = self.app.get('/', headers={'Accept': 'text/html'})

        assert 'Fedora Updates System' in resp
        assert '&copy;' in resp
        assert 'Legal</a>' in resp
        assert 'http://loweringthebar.net/' in resp

    def test_home_html_no_legal(self):
        """Test the home page HTML when no legal link is configured."""
        with mock.patch.dict(self.registry.settings, {'legal_link': ''}):
            resp = self.app.get('/', headers={'Accept': 'text/html'})

        assert 'Fedora Updates System' in resp
        assert '&copy;' in resp
        assert 'Legal</a>' not in resp
        assert 'http://loweringthebar.net/' not in resp

    def test_edit_add_build_from_different_release(self):
        """Editing an update that references builds from other releases should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = 'testing!!!'
        update_json['edited'] = update.alias
        update_json['builds'] = update_json['builds'] + ',bodhi-3.2.0-1.fc27'
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            'status': 'error',
            'errors': [
                {'description': (
                    "Cannot find release associated with build: bodhi-3.2.0-1.fc27, "
                    "tags: {}".format(['f27-updates-candidate', 'f27', 'f27-updates-testing'])),
                 'location': 'body', 'name': 'builds'}]}
        assert res.json == expected_json

    def test_edit_invalidly_tagged_build(self):
        """Editing an update that references invalidly tagged builds should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = 'testing!!!'
        update_json['edited'] = update.alias
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                        return_value=[{'name': 'f17-updates'}]) as listTags:
            res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            'status': 'error',
            'errors': [
                {'description': (
                    "Invalid tag: bodhi-2.0-1.fc17 not tagged with any of the following tags "
                    "{}".format(['f17-updates-candidate', 'f17-updates-testing'])),
                 'location': 'body', 'name': 'builds'}]}
        assert res.json == expected_json
        listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    def test_edit_koji_error(self):
        """Editing an update that references missing builds should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = 'testing!!!'
        update_json['edited'] = update.alias
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                        side_effect=koji.GenericError()) as listTags:
            res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            'status': 'error',
            'errors': [
                {'description': 'Invalid koji build: bodhi-2.0-1.fc17', 'location': 'body',
                 'name': 'builds'}]}
        assert res.json == expected_json
        listTags.assert_called_once_with(update.title)

    def test_edit_untagged_build(self):
        """Editing an update that references untagged builds should raise an error."""
        update = self.db.query(Update).one()
        update_json = self.get_update(update.title)
        update_json['csrf_token'] = self.get_csrf_token()
        update_json['notes'] = 'testing!!!'
        update_json['edited'] = update.alias
        # This will cause an extra error in the output that we aren't testing here, so delete it.
        del update_json['requirements']

        with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                        return_value=[]) as listTags:
            res = self.app.post_json('/updates/', update_json, status=400)

        expected_json = {
            'status': 'error',
            'errors': [
                {'description': 'Cannot find any tags associated with build: bodhi-2.0-1.fc17',
                 'location': 'body', 'name': 'builds'},
                {'description': (
                    "Cannot find release associated with build: bodhi-2.0-1.fc17, "
                    "tags: []"),
                 'location': 'body', 'name': 'builds'}]}
        assert res.json == expected_json
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
        assert locked_notice in resp
        assert '<span class="sr-only">Locked</span>' in resp
        assert '/composes/{}/{}'.format(compose.release.name, compose.request.value) in resp

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_edit_anything(self, *args):
        "Ensure provenpackagers can edit updates for any package"
        nvr = 'bodhi-2.1-1.fc17'

        user = User(name='lloyd')
        user2 = User(name='ralph')
        self.db.add(user)
        self.db.add(user2)  # Add a packager but not proventester
        self.db.commit()
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        group2 = self.db.query(Group).filter_by(name='packager').one()
        user2.groups.append(group2)

        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='ralph', session=self.db, **self.app_settings))
        up_data = self.get_update(nvr)
        up_data['csrf_token'] = app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = app.post_json('/updates/', up_data)

        assert 'does not have commit access to bodhi' not in res
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='lloyd', session=self.db, **self.app_settings))
        update = self.get_update(nvr)
        update['csrf_token'] = app.get('/csrf').json_body['csrf_token']
        update['notes'] = 'testing!!!'
        update['edited'] = res.json['alias']

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            res = app.post_json('/updates/', update)

        assert 'bodhi does not have commit access to bodhi' not in res
        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        assert build.update is not None
        assert build.update.notes == 'testing!!!'

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_request_privs(self, *args):
        "Ensure provenpackagers can change the request for any update"
        nvr = 'bodhi-2.1-1.fc17'
        user = User(name='bob')
        user2 = User(name='ralph')
        self.db.add(user)
        self.db.add(user2)  # Add a packager but not proventester
        self.db.add(User(name='someuser'))  # An unrelated user with no privs
        self.db.commit()
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        group2 = self.db.query(Group).filter_by(name='packager').one()
        user2.groups.append(group2)

        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='ralph', session=self.db, **self.app_settings))
        up_data = self.get_update(nvr)
        up_data['csrf_token'] = app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = app.post_json('/updates/', up_data)

        assert 'does not have commit access to bodhi' not in res
        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.passed
        assert build.update.request == UpdateRequest.testing

        # Try and submit the update to stable as a non-provenpackager
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='ralph', session=self.db, **self.app_settings))
        post_data = dict(update=nvr, request='stable',
                         csrf_token=app.get('/csrf').json_body['csrf_token'])
        res = app.post_json(f"/updates/{res.json['alias']}/request", post_data, status=400)

        # Ensure we can't push it until it meets the requirements
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == config.get('not_yet_tested_msg')

        update = Build.query.filter_by(nvr=nvr).one().update
        assert update.stable_karma == 3
        assert update.locked is False
        assert update.request == UpdateRequest.testing

        # Pretend it was pushed to testing
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        assert update.karma == 0
        update.comment(self.db, "foo", 1, 'foo')
        update = Build.query.filter_by(nvr=nvr).one().update
        assert update.karma == 1
        assert update.request is None
        update.comment(self.db, "foo", 1, 'bar')
        update = Build.query.filter_by(nvr=nvr).one().update
        assert update.karma == 2
        assert update.request is None
        with fml_testing.mock_sends(api.Message, api.Message, api.Message):
            update.comment(self.db, "foo", 1, 'biz')
        update = Build.query.filter_by(nvr=nvr).one().update
        assert update.karma == 3
        assert update.request == UpdateRequest.stable
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        # Set it back to testing
        update.request = UpdateRequest.testing

        # Try and submit the update to stable as a proventester
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='bob', session=self.db, **self.app_settings))

        with fml_testing.mock_sends(update_schemas.UpdateRequestStableV1):
            res = app.post_json(f'/updates/{update.alias}/request',
                                dict(update=nvr, request='stable',
                                     csrf_token=app.get('/csrf').json_body['csrf_token']),
                                status=200)

        assert res.json_body['update']['request'] == 'stable'

        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='bob', session=self.db, **self.app_settings))

        with fml_testing.mock_sends(update_schemas.UpdateRequestObsoleteV1):
            res = app.post_json(f'/updates/{update.alias}/request',
                                dict(update=nvr, request='obsolete',
                                     csrf_token=app.get('/csrf').json_body['csrf_token']),
                                status=200)

        assert res.json_body['update']['request'] is None
        # We need to re-fetch the update from the database since the post calls committed the
        # transaction.
        update = Build.query.filter_by(nvr=nvr).one().update
        assert update.request is None
        assert update.status == UpdateStatus.obsolete

        # Test that bob has can_edit True, provenpackager
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='bob', session=self.db, **self.app_settings))

        res = app.get(f'/updates/{update.alias}', status=200)
        assert res.json_body['can_edit'] is True

        # Test that ralph has can_edit True, they submitted it.
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='ralph', session=self.db, **self.app_settings))

        res = app.get(f'/updates/{update.alias}', status=200)
        assert res.json_body['can_edit'] is True

        # Test that someuser has can_edit False, they are unrelated
        # This check *failed* with the old acls code.
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing='someuser', session=self.db, **self.app_settings))

        res = app.get(f'/updates/{update.alias}', status=200)
        assert res.json_body['can_edit'] is False

        # Test that an anonymous user has can_edit False, obv.
        # This check *crashed* with the code on 2015-09-24.
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })

        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, session=self.db, **anonymous_settings))

        res = app.get(f'/updates/{update.alias}', status=200)
        assert res.json_body['can_edit'] is False

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_request_update_queued_in_test_gating(self, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `queued`"""
        nvr = 'bodhi-2.1-1.fc17'
        user = User(name='bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = self.app.post_json('/updates/', up_data)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.queued
        assert build.update.request == UpdateRequest.testing

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json(f'/updates/{build.update.alias}/request',
                                     post_data, status=400)

        # Ensure we can't push it until it passed test gating
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            'Requirement not met Required tests did not pass on this update'
        )

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_request_update_running_in_test_gating(self, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `running`"""
        nvr = 'bodhi-2.1-1.fc17'
        user = User(name='bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = self.app.post_json('/updates/', up_data)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.running
        assert build.update.request == UpdateRequest.testing

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json(f'/updates/{build.update.alias}/request',
                                     post_data, status=400)

        # Ensure we can't push it until it passed test gating
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            'Requirement not met Required tests did not pass on this update'
        )

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_request_update_failed_test_gating(self, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `failed`"""
        nvr = 'bodhi-2.1-1.fc17'
        user = User(name='bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = self.app.post_json('/updates/', up_data)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.failed
        assert build.update.request == UpdateRequest.testing

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json(f'/updates/{build.update.alias}/request',
                                     post_data, status=400)

        # Ensure we can't push it until it passed test gating
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            'Requirement not met Required tests did not pass on this update'
        )

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_request_update_ignored_by_test_gating(self, *args):
        """Ensure provenpackagers can request changes for any update which
        test gating status is `ignored`"""
        nvr = 'bodhi-2.1-1.fc17'
        user = User(name='bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = self.app.post_json('/updates/', up_data)

        assert 'does not have commit access to bodhi' not in res
        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.ignored
        assert build.update.request == UpdateRequest.testing

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json(f'/updates/{build.update.alias}/request',
                                     post_data, status=400)

        # Ensure the reason we cannot push isn't test gating this time
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == config.get('not_yet_tested_msg')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_request_update_waiting_on_test_gating(self, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `waiting`"""
        nvr = 'bodhi-2.1-1.fc17'
        user = User(name='bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = self.app.post_json('/updates/', up_data)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = TestGatingStatus.waiting
        assert build.update.request == UpdateRequest.testing

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json(f'/updates/{build.update.alias}/request',
                                     post_data, status=400)

        # Ensure we can't push it until it passed test gating
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            'Requirement not met Required tests did not pass on this update'
        )

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_provenpackager_request_update_with_none_test_gating(self, *args):
        """Ensure provenpackagers cannot request changes for any update which
        test gating status is `None`"""
        nvr = 'bodhi-2.1-1.fc17'
        user = User(name='bob')
        self.db.add(user)
        group = self.db.query(Group).filter_by(name='provenpackager').one()
        user.groups.append(group)
        self.db.commit()

        up_data = self.get_update(nvr)
        up_data['csrf_token'] = self.app.get('/csrf').json_body['csrf_token']

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            res = self.app.post_json('/updates/', up_data)

        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        build.update.test_gating_status = None
        assert build.update.request == UpdateRequest.testing

        # Try and submit the update to stable as a provenpackager
        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        with mock.patch.dict(config, {'test_gating.required': True}):
            res = self.app.post_json(f'/updates/{build.update.alias}/request',
                                     post_data, status=400)

        # Ensure the reason we can't push is not test gating
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == config.get('not_yet_tested_msg')

    def test_404(self):
        self.app.get('/a', status=404)

    def test_get_single_update(self):
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        res = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'application/json'})

        assert res.json_body['update']['title'] == 'bodhi-2.0-1.fc17'
        version_hash = "19504edccbed061be0b47741238859a94d973138"
        assert res.json_body['update']['version_hash'] == version_hash
        assert 'application/json' in res.headers['Content-Type']

    def test_get_single_update_jsonp(self):
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        res = self.app.get(f'/updates/{update.alias}',
                           {'callback': 'callback'},
                           headers={'Accept': 'application/javascript'})

        assert 'application/javascript' in res.headers['Content-Type']
        assert 'callback' in res
        assert 'bodhi-2.0-1.fc17' in res

    def test_get_single_update_rss_fail_406(self):
        """Test a 406 return status if we try to get a single update via rss."""
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        self.app.get(f'/updates/{update.alias}',
                     headers={'Accept': 'application/atom+xml'},
                     status=406)

    def test_get_single_update_html_no_privacy_link(self):
        """Test getting a single update via HTML when no privacy link is configured."""
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        with mock.patch.dict(self.registry.settings, {'privacy_link': ''}):
            resp = self.app.get(f'/updates/{update.alias}',
                                headers={'Accept': 'text/html'})

        assert 'text/html' in resp.headers['Content-Type']
        assert update.builds[0].nvr in resp
        assert '&copy;' in resp
        # The privacy policy comment should not be written on the page since by default Bodhi
        # doesn't have a configured privacy policy.
        assert 'privacy' not in resp

    def test_get_single_update_html_privacy_link(self):
        """Test getting a single update via HTML when a privacy link is configured."""
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        with mock.patch.dict(
                self.registry.settings,
                {'privacy_link': 'https://privacyiscool.com'}):
            resp = self.app.get(f'/updates/{update.alias}',
                                headers={'Accept': 'text/html'})

        assert 'text/html' in resp.headers['Content-Type']
        assert update.builds[0].nvr in resp
        assert '&copy;' in resp
        # The privacy policy comment should not be written on the page since by default Bodhi
        # doesn't have a configured privacy policy.
        assert 'Privacy policy' in resp
        assert 'https://privacyiscool.com' in resp
        assert 'Comments are governed under' in resp

    def test_xss(self):
        """Assert that user input is sanitized."""
        update = Update.query.one()
        update.display_name = "<script>thisIsBad()</script>"
        update.requirements = "<script>thisIsBad()</script>"
        self.db.commit()

        res = self.app.get(f'/updates/{update.alias}', status=200, headers={'Accept': 'text/html'})
        assert "<script>thisIsBad()</script>" not in res.text
        assert res.text.count("&lt;script&gt;thisIsBad()&lt;/script&gt;") == 3

    def test_list_updates(self):
        res = self.app.get('/updates/')
        body = res.json_body
        assert len(body['updates']) == 1

        alias = f'FEDORA-{YEAR}-a3bbe1a8f2'

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'rpm'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == alias
        assert up['karma'] == 1
        assert up['url'] == urlparse.urljoin(config['base_address'], f'/updates/{alias}')

    def test_list_updates_jsonp(self):
        res = self.app.get('/updates/',
                           {'callback': 'callback'},
                           headers={'Accept': 'application/javascript'})
        assert 'application/javascript' in res.headers['Content-Type']
        assert 'callback' in res
        assert 'bodhi-2.0-1.fc17' in res

    def test_list_updates_rss(self):
        res = self.app.get('/rss/updates/',
                           headers={'Accept': 'application/atom+xml'})
        assert 'application/rss+xml' in res.headers['Content-Type']
        assert f'FEDORA-{datetime.utcnow().year}-a3bbe1a8f2' in res
        assert 'Released updates' in res
        assert 'All updates' in res

    def test_list_updates_rss_formatting(self):
        """Test the formatting of update description in rss feed."""
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update_details = f'<h1>FEDORA-{datetime.utcnow().year}-a3bbe1a8f2</h1>\n' \
                         f'<h2>Packages in this update:</h2>\n' \
                         f'<ul>\n<li>bodhi-2.0-1.fc17</li>\n</ul>\n' \
                         f'<h2>Update description:</h2>\n' \
                         f'<p>Useful details!</p>'
        res = self.app.get('/rss/updates/',
                           headers={'Accept': 'application/atom+xml'})
        assert 'application/rss+xml' in res.headers['Content-Type']
        assert f'<title>{update.title}</title>' in res
        assert f'<link>http://localhost/{update.get_url()}</link>' in res
        assert escape(update_details) in res

    def test_list_updates_rss_with_single_filter(self):
        res = self.app.get('/rss/updates/', {'severity': 'low'},
                           headers={'Accept': 'application/atom+xml'})
        assert 'application/rss+xml' in res.headers['Content-Type']
        assert 'Released updates' in res
        assert 'Filtered on: severity(low)' in res

    def test_list_updates_rss_with_multiple_filters(self):
        res = self.app.get('/rss/updates/', {'severity': 'low', 'type': 'security'},
                           headers={'Accept': 'application/atom+xml'})
        assert 'application/rss+xml' in res.headers['Content-Type']
        assert 'Released updates' in res
        assert 'type(security)' in res
        assert 'severity(low)' in res

    def test_list_updates_html(self):
        res = self.app.get('/updates/',
                           headers={'Accept': 'text/html'})
        assert 'text/html' in res.headers['Content-Type']
        assert 'bodhi-2.0-1.fc17' in res
        assert '&copy;' in res

    def test_updates_like(self):
        res = self.app.get('/updates/', {'like': 'odh'})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

        res = self.app.get('/updates/', {'like': 'wat'})
        body = res.json_body
        assert not body['updates']

    def test_updates_search(self):
        """
        Test that the updates/?search= endpoint works as expected
        """

        # test that the search works
        res = self.app.get('/updates/', {'search': 'bodh'})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

        # test that the search is case insensitive
        res = self.app.get('/updates/', {'search': 'Bodh'})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

        # test a search that yields nothing
        res = self.app.get('/updates/', {'search': 'wat'})
        body = res.json_body
        assert not body['updates']

        # test a search for an alias
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        res = self.app.get(
            '/updates/', {'search': update.alias})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

        # test that the search works for leading space
        res = self.app.get('/updates/', {'search': ' bodh'})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

        # test that the search works for trailing space
        res = self.app.get('/updates/', {'search': 'bodh '})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

        # test that the search works for both leading and trailing space
        res = self.app.get('/updates/', {'search': ' bodh '})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

    @mock.patch(**mock_valid_requirements)
    def test_list_updates_pagination(self, *args):

        # First, stuff a second update in there
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-2.fc17'))

        # Then, test pagination
        res = self.app.get('/updates/',
                           {"rows_per_page": 1})
        body = res.json_body
        assert len(body['updates']) == 1
        update1 = body['updates'][0]

        res = self.app.get('/updates/',
                           {"rows_per_page": 1, "page": 2})
        body = res.json_body
        assert len(body['updates']) == 1
        update2 = body['updates'][0]

        assert update1 != update2

    def test_list_updates_by_approved_since(self):
        now = datetime.utcnow()

        # Try with no approved updates first
        res = self.app.get('/updates/',
                           {"approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert not body['updates']

        # Now approve one
        self.db.query(Update).first().date_approved = now
        self.db.commit()

        # And try again
        res = self.app.get('/updates/',
                           {"approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'rpm'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_approved'] == now.strftime("%Y-%m-%d %H:%M:%S")
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert len(up['bugs']) == 1
        assert up['bugs'][0]['bug_id'] == 12345

        # https://github.com/fedora-infra/bodhi/issues/270
        assert len(up['test_cases']) == 1
        assert up['test_cases'][0]['name'] == 'Wat'

    def test_list_updates_by_invalid_approved_since(self):
        res = self.app.get('/updates/', {"approved_since": "forever"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'approved_since'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_approved_before(self):
        # Approve an update
        now = datetime.utcnow()
        self.db.query(Update).first().date_approved = now
        self.db.commit()

        # First check we get no result for an old date
        res = self.app.get('/updates/',
                           {"approved_before": "1984-11-01"})
        body = res.json_body
        assert not body['updates']

        # Now check we get the update if we use tomorrow
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        res = self.app.get('/updates/', {"approved_before": tomorrow})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['content_type'] == 'rpm'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_approved'] == now.strftime("%Y-%m-%d %H:%M:%S")
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert len(up['bugs']) == 1
        assert up['bugs'][0]['bug_id'] == 12345

    def test_list_updates_by_invalid_approved_before(self):
        res = self.app.get('/updates/', {"approved_before": "forever"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'approved_before'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_bugs(self):
        res = self.app.get('/updates/', {"bugs": '12345'})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert len(up['bugs']) == 1
        assert up['bugs'][0]['bug_id'] == 12345

    def test_list_updates_by_invalid_bug(self):
        res = self.app.get('/updates/', {"bugs": "cockroaches"}, status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'bugs'
        assert body['errors'][0]['description'] == (
            "Invalid bug ID specified: {}".format(['cockroaches'])
        )

    def test_list_updates_by_nonexistent_bug(self):
        res = self.app.get('/updates/', {"bugs": "19850110"})
        body = res.json_body
        assert not body['updates']

    def test_list_updates_by_critpath(self):
        res = self.app.get('/updates/', {"critpath": "false"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_invalid_critpath(self):
        res = self.app.get('/updates/', {"critpath": "lalala"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'critpath'
        assert body['errors'][0]['description'] == (
            '"lalala" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')'
        )

    def test_list_updates_by_date_submitted_invalid_date(self):
        """test filtering by submitted date with an invalid date"""
        res = self.app.get('/updates/', {"submitted_since": "11-01-1984"}, status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'submitted_since'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_date_submitted_future_date(self):
        """test filtering by submitted date with future date"""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        res = self.app.get('/updates/', {"submitted_since": tomorrow})
        body = res.json_body
        assert not body['updates']

    def test_list_updates_by_date_submitted_valid(self):
        """test filtering by submitted date with valid data"""
        res = self.app.get('/updates/', {"submitted_since": "1984-11-01"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_date_submitted_before_invalid_date(self):
        """test filtering by submitted before date with an invalid date"""
        res = self.app.get('/updates/', {"submitted_before": "11-01-1984"}, status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'submitted_before'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_date_submitted_before_old_date(self):
        """test filtering by submitted before date with old date"""
        res = self.app.get('/updates/', {"submitted_before": "1975-01-01"})
        body = res.json_body
        assert not body['updates']

    def test_list_updates_by_date_submitted_before_valid(self):
        """test filtering by submitted before date with valid date"""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        res = self.app.get('/updates/', {"submitted_before": today})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_locked(self):
        Update.query.one().locked = True
        self.db.flush()
        res = self.app.get('/updates/', {"locked": "true"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is True
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_content_type(self):
        res = self.app.get('/updates/', {"content_type": "module"})
        body = res.json_body
        assert not body['updates']

        res = self.app.get('/updates/', {"content_type": "rpm"})
        body = res.json_body
        assert len(body['updates']) == 1

    def test_list_updates_by_invalid_locked(self):
        res = self.app.get('/updates/', {"locked": "maybe"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'locked'
        assert body['errors'][0]['description'] == (
            '"maybe" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')'
        )

    def test_list_updates_by_modified_since(self):
        now = datetime.utcnow()

        # Try with no modified updates first
        res = self.app.get('/updates/',
                           {"modified_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert not body['updates']

        # Now approve one
        self.db.query(Update).first().date_modified = now
        self.db.commit()

        # And try again
        res = self.app.get('/updates/',
                           {"modified_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] == now.strftime("%Y-%m-%d %H:%M:%S")
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert len(up['bugs']) == 1
        assert up['bugs'][0]['bug_id'] == 12345

    def test_list_updates_by_invalid_modified_since(self):
        res = self.app.get('/updates/', {"modified_since": "the dawn of time"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'modified_since'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_modified_before(self):
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        # Try with no modified updates first
        res = self.app.get('/updates/',
                           {"modified_before": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert not body['updates']

        # Now approve one
        self.db.query(Update).first().date_modified = now
        self.db.commit()

        # And try again
        res = self.app.get('/updates/',
                           {"modified_before": tomorrow})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] == now.strftime("%Y-%m-%d %H:%M:%S")
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert len(up['bugs']) == 1
        assert up['bugs'][0]['bug_id'] == 12345

    def test_list_updates_by_invalid_modified_before(self):
        res = self.app.get('/updates/', {"modified_before": "the dawn of time"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'modified_before'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_package(self):
        res = self.app.get('/updates/', {"packages": "bodhi"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_builds(self):
        res = self.app.get('/updates/', {"builds": "bodhi-3.0-1.fc17"})
        body = res.json_body
        assert not body['updates']

        res = self.app.get('/updates/', {"builds": "bodhi-2.0-1.fc17"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_nonexistent_package(self):
        res = self.app.get('/updates/', {"packages": "flash-player"})
        body = res.json_body
        assert not body['updates']

    def test_list_updates_by_pushed(self):
        res = self.app.get('/updates/', {"pushed": "false"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert up['pushed'] is False

    def test_list_updates_by_invalid_pushed(self):
        res = self.app.get('/updates/', {"pushed": "who knows?"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'pushed'
        assert body['errors'][0]['description'] == (
            '"who knows?" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')'
        )

    def test_list_updates_by_pushed_since(self):
        now = datetime.utcnow()

        # Try with no pushed updates first
        res = self.app.get('/updates/',
                           {"pushed_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert not body['updates']

        # Now approve one
        self.db.query(Update).first().date_pushed = now
        self.db.commit()

        # And try again
        res = self.app.get('/updates/',
                           {"pushed_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_approved'] is None
        assert up['date_pushed'] == now.strftime("%Y-%m-%d %H:%M:%S")
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert len(up['bugs']) == 1
        assert up['bugs'][0]['bug_id'] == 12345

    def test_list_updates_by_invalid_pushed_since(self):
        res = self.app.get('/updates/', {"pushed_since": "a while ago"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'pushed_since'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_pushed_before(self):
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        # Try with no pushed updates first
        res = self.app.get('/updates/',
                           {"pushed_before": now.strftime("%Y-%m-%d")})
        body = res.json_body
        assert not body['updates']

        # Now approve one
        self.db.query(Update).first().date_pushed = now
        self.db.commit()

        # And try again
        res = self.app.get('/updates/',
                           {"pushed_before": tomorrow})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_approved'] is None
        assert up['date_pushed'] == now.strftime("%Y-%m-%d %H:%M:%S")
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1
        assert len(up['bugs']) == 1
        assert up['bugs'][0]['bug_id'] == 12345

    def test_list_updates_by_invalid_pushed_before(self):
        res = self.app.get('/updates/', {"pushed_before": "a while ago"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'pushed_before'
        assert body['errors'][0]['description'] == 'Invalid date'

    def test_list_updates_by_release_name(self):
        res = self.app.get('/updates/', {"releases": "F17"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_singular_release_param(self):
        """
        Test the singular parameter "release" rather than "releases".
        Note that "release" is purely for bodhi1 compat (mostly RSS feeds)
        """
        res = self.app.get('/updates/', {"release": "F17"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_release_version(self):
        res = self.app.get('/updates/', {"releases": "17"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_nonexistent_release(self):
        res = self.app.get('/updates/', {"releases": "WinXP"}, status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'releases'
        assert body['errors'][0]['description'] == 'Invalid releases specified: WinXP'

    def test_list_updates_by_releases_pending(self, create_quick_filters_data):
        """Test the quick filter for all pending releases."""
        res = self.app.get('/updates/', {"releases": "__pending__"})
        body = res.json_body
        assert len(body['updates']) == 1
        assert body['updates'][0]['title'] == 'shiny_new-7.8.9-1.fc40'

    def test_list_updates_by_releases_current(self, create_quick_filters_data):
        """Test the quick filter for all current releases."""
        res = self.app.get('/updates/', {"releases": "__current__"})
        body = res.json_body
        assert len(body['updates']) == 1
        assert body['updates'][0]['title'] == 'bodhi-2.0-1.fc17'

    def test_list_updates_by_releases_archived(self, create_quick_filters_data):
        """Test the quick filter for all archived releases."""
        res = self.app.get('/updates/', {"releases": "__archived__"})
        body = res.json_body
        assert len(body['updates']) == 1
        assert body['updates'][0]['title'] == 'really_old-1.2.3-1.fc20'

    def test_list_updates_by_releases_current_and_specific(self, create_quick_filters_data):
        """Test updates list for quick filter OR a specific release."""
        res = self.app.get('/updates/', {"releases": ["__current__", "F20"]})
        body = res.json_body
        assert len(body['updates']) == 2
        assert body['updates'][0]['title'] == 'really_old-1.2.3-1.fc20'
        assert body['updates'][1]['title'] == 'bodhi-2.0-1.fc17'

    def test_list_updates_by_request(self):
        res = self.app.get('/updates/', {'request': "testing"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_nonexistent_request(self):
        res = self.app.get('/updates/', {"request": "impossible"},
                           status=400)
        body = res.json_body
        request_vals = ", ".join(UpdateRequest.values())
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'request'
        assert body['errors'][0]['description'] == (
            f'"impossible" is not one of {request_vals}'
        )

    def test_list_updates_by_severity(self):
        res = self.app.get('/updates/', {"severity": "medium"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_nonexistent_severity(self):
        res = self.app.get('/updates/', {"severity": "schoolmaster"},
                           status=400)
        body = res.json_body
        severity_vals = ", ".join(UpdateSeverity.values())
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'severity'
        assert body['errors'][0]['description'] == (
            f'"schoolmaster" is not one of {severity_vals}'
        )

    def test_list_updates_by_status(self):
        res = self.app.get('/updates/', {"status": "pending"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_nonexistent_status(self):
        res = self.app.get('/updates/', {"status": "single"},
                           status=400)
        body = res.json_body
        status_vals = ", ".join(UpdateStatus.values())
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'status.0'
        assert body['errors'][0]['description'] == f'"single" is not one of {status_vals}'

    def test_list_updates_with_multiple_statuses(self):
        # add two more updates with different statuses. we
        # will only test for one of these, and the bodhi one
        # that is in the testing db by default
        firefox = self.create_update(['firefox-61.0.2-3.fc17'])
        firefox.status = UpdateStatus.unpushed
        python_nose = self.create_update(['python-nose-1.3.7-11.fc17'])
        python_nose.status = UpdateStatus.testing
        self.db.commit()

        res = self.app.get('/updates/', {"status": ["pending", "testing"]})
        body = res.json_body
        assert len(body['updates']) == 2
        expected = ['bodhi-2.0-1.fc17', 'python-nose-1.3.7-11.fc17']
        actual = sorted(update['title'] for update in body['updates'])
        assert expected == actual

    def test_list_updates_by_suggest(self):
        res = self.app.get('/updates/', {"suggest": "unspecified"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_nonexistent_suggest(self):
        res = self.app.get('/updates/', {"suggest": "no idea"},
                           status=400)
        body = res.json_body
        suggest_vals = ", ".join(UpdateSuggestion.values())
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'suggest'
        assert body['errors'][0]['description'] == (
            f'"no idea" is not one of {suggest_vals}'
        )

    def test_list_updates_by_type(self):
        res = self.app.get('/updates/', {"type": "bugfix"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_nonexistent_type(self):
        res = self.app.get('/updates/', {"type": "not_my"},
                           status=400)
        body = res.json_body
        type_vals = ", ".join(UpdateType.values())
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'type'
        assert body['errors'][0]['description'] == f'"not_my" is not one of {type_vals}'

    def test_list_updates_by_username(self):
        res = self.app.get('/updates/', {"user": "guest"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_gating_status(self):
        up = self.db.query(Build).filter_by(nvr='bodhi-2.0-1.fc17').one().update
        up.test_gating_status = TestGatingStatus.passed
        self.db.commit()
        res = self.app.get('/updates/', {"gating": "passed"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_from_side_tag(self):
        up = self.db.query(Build).filter_by(nvr='bodhi-2.0-1.fc17').one().update
        up.from_tag = 'f33-side-tag'
        self.db.commit()
        res = self.app.get('/updates/', {"from_side_tag": "true"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_not_from_side_tag(self):
        res = self.app.get('/updates/', {"from_side_tag": "false"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'medium'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'Useful details!'
        assert up['date_submitted'] == '1984-11-02 00:00:00'
        assert up['date_modified'] is None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-a3bbe1a8f2'
        assert up['karma'] == 1

    def test_list_updates_by_multiple_usernames(self):
        another_user = User(name='aUser')
        self.db.add(another_user)
        update = Update(
            user=another_user,
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes='Just another update.',
            date_submitted=datetime(1981, 10, 11),
            requirements='rpmlint',
            stable_karma=3,
            unstable_karma=-3,
            release=Release.query.one()
        )
        self.db.add(update)
        self.db.flush()

        res = self.app.get('/updates/', {"user": "guest,aUser"})
        body = res.json_body
        assert len(body['updates']) == 2

        assert body['updates'][0]['title'] == 'bodhi-2.0-1.fc17'
        # This one uses alias because it doesn't have any builds associated with it yet.
        assert body['updates'][1]['title'] == body['updates'][1]['alias']
        assert body['updates'][0]['user']['name'] == 'guest'
        assert body['updates'][1]['user']['name'] == 'aUser'

    def test_list_updates_by_nonexistent_username(self):
        res = self.app.get('/updates/', {"user": "santa"},
                           status=400)
        body = res.json_body
        assert not body.get('updates')
        assert body['errors'][0]['name'] == 'user'
        assert body['errors'][0]['description'] == "Invalid users specified: santa"

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_edit_update(self, *args):
        args = self.get_update('bodhi-2.0.0-2.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        args['edited'] = r.json['alias']
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        args['requirements'] = 'upgradepath'

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'unspecified'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'this is a test update'
        assert up['date_submitted'] is not None
        assert up['date_modified'] is not None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-033713b73b'
        assert up['karma'] == 0
        assert up['requirements'] == 'upgradepath'
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17

        Karma has been reset.
        """).strip()
        assert_multiline_equal(up['comments'][-1]['text'], comment)
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-3.fc17'
        assert self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first() is None

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_uuid4_version1)
    @mock.patch(**mock_valid_requirements)
    def test_edit_rpm_update_from_tag(self, *args):
        """Test editing an update using (updated) builds from a Koji tag."""
        # We don't want the new update to obsolete the existing one.
        self.db.delete(Update.query.one())

        # We need a release that isn't composed by bodhi
        release = Release.query.one()
        release.composed_by_bodhi = False
        self.db.commit()

        # We don't want an existing buildroot override to clutter the messages.
        self.db.delete(BuildrootOverride.query.one())

        update = self.get_update(from_tag='f17-build-side-7777')
        with mock.patch('bodhi.server.buildsys.DevBuildsys.getTag', self.mock_getTag):
            r = self.app.post_json('/updates/', update)

        update['edited'] = r.json['alias']
        update['builds'] = 'bodhi-2.0.0-3.fc17'
        update['requirements'] = 'upgradepath'

        with mock.patch('bodhi.server.buildsys.DevBuildsys.getTag', self.mock_getTag):
            with fml_testing.mock_sends(update_schemas.UpdateEditV1):
                r = self.app.post_json('/updates/', update)

        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['status'] == 'pending'
        assert up['request'] is None
        assert up['user']['name'] == 'guest'
        assert up['release']['name'] == 'F17'
        assert up['type'] == 'bugfix'
        assert up['severity'] == 'unspecified'
        assert up['suggest'] == 'unspecified'
        assert up['close_bugs'] is True
        assert up['notes'] == 'this is a test update'
        assert up['date_submitted'] is not None
        assert up['date_modified'] is not None
        assert up['date_approved'] is None
        assert up['date_pushed'] is None
        assert up['locked'] is False
        assert up['alias'] == f'FEDORA-{YEAR}-033713b73b'
        assert up['karma'] == 0
        assert up['requirements'] == 'upgradepath'
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0-1.fc17

        Karma has been reset.
        """).strip()
        assert_multiline_equal(up['comments'][-1]['text'], comment)
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-3.fc17'
        assert self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first() is None

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.models.tag_update_builds_task')
    @mock.patch('bodhi.server.models.Build.get_tags')
    @mock.patch('bodhi.server.models.log.info')
    def test_edit_pending_update_with_new_builds(self, info, get_tags, tag_task, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as pending
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.pending
        upd.request = UpdateRequest.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        get_tags.return_value = ['f17-updates-candidate',
                                 'f17-updates-testing-pending']

        args['edited'] = upd.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        info.assert_any_call('Unpushing bodhi-2.0.0-2.fc17')
        info.assert_any_call('Removing f17-updates-testing-pending tag from bodhi-2.0.0-2.fc17')
        assert mock.call(
            'Removing f17-updates-candidate tag from bodhi-2.0.0-2.fc17'
        ) not in info.call_args_list
        tag_task.delay.assert_called_once_with(tag='f17-updates-signing-pending',
                                               builds=['bodhi-2.0.0-3.fc17'])
        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17

        Karma has been reset.
        """).strip()
        assert_multiline_equal(up['comments'][-1]['text'], comment)
        assert up['comments'][-3]['text'] == 'This update has been submitted for testing by guest. '
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-3.fc17'
        assert self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first() is None

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.models.tag_update_builds_task')
    @mock.patch('bodhi.server.models.Build.get_tags')
    @mock.patch('bodhi.server.models.log.info')
    def test_edit_testing_update_with_new_builds(self, info, get_tags, tag_task, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = None
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        get_tags.return_value = ['f17-updates-testing']

        args['edited'] = upd.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1,
                                    update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        info.assert_any_call('Unpushing bodhi-2.0.0-2.fc17')
        info.assert_any_call(
            'Moving bodhi-2.0.0-2.fc17 from f17-updates-testing to f17-updates-candidate')
        tag_task.delay.assert_called_once_with(tag='f17-updates-signing-pending',
                                               builds=['bodhi-2.0.0-3.fc17'])
        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['comments'][-1]['text'] == 'This update has been submitted for testing by guest. '
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17

        Karma has been reset.
        """).strip()
        assert_multiline_equal(up['comments'][-2]['text'], comment)
        assert up['comments'][-4]['text'] == 'This update has been submitted for testing by guest. '
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-3.fc17'
        assert self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first() is None

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.models.tag_update_builds_task')
    @mock.patch('bodhi.server.models.Build.get_tags')
    @mock.patch('bodhi.server.models.log.info')
    def test_edit_testing_update_with_new_builds_with_stable_request(self, info, get_tags,
                                                                     tag_task, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = UpdateRequest.stable
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        get_tags.return_value = ['f17-updates-testing',
                                 'f17-updates-pending']

        args['edited'] = upd.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1,
                                    update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        info.assert_any_call('Unpushing bodhi-2.0.0-2.fc17')
        info.assert_any_call('Removing f17-updates-pending tag from bodhi-2.0.0-2.fc17')
        info.assert_any_call(
            'Moving bodhi-2.0.0-2.fc17 from f17-updates-testing to f17-updates-candidate')
        tag_task.delay.assert_called_once_with(tag='f17-updates-signing-pending',
                                               builds=['bodhi-2.0.0-3.fc17'])
        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['comments'][-1]['text'] == 'This update has been submitted for testing by guest. '
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17

        Karma has been reset.
        """).strip()
        assert_multiline_equal(up['comments'][-2]['text'], comment)
        assert up['comments'][-4]['text'] == 'This update has been submitted for testing by guest. '
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-3.fc17'
        assert self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first() is None

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    def test_edit_testing_update_with_stable_request_no_edit_build(self, *args):
        """An update with stable request should not be pushed back to testing if
        build list is not changed."""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = UpdateRequest.stable
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        args['edited'] = upd.alias
        args['notes'] = 'A nifty description.'

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-2.fc17'
        assert up['status'] == 'testing'
        assert up['request'] == 'stable'
        assert up['notes'] == 'A nifty description.'
        assert up['comments'][-1]['text'] == 'guest edited this update.'
        assert up['comments'][-3]['text'] == 'This update has been submitted for testing by guest. '
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-2.fc17'

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.models.tag_update_builds_task')
    @mock.patch('bodhi.server.models.Build.get_tags')
    @mock.patch('bodhi.server.models.log.info')
    def test_edit_pending_sidetag_update_with_new_builds(self, info, get_tags, tag_task, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as pending
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.pending
        upd.request = UpdateRequest.testing
        upd.from_tag = 'f17-build-side-12345'
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        get_tags.return_value = ['f17-updates-candidate',
                                 'f17-updates-testing-pending',
                                 'f17-build-side-12345']

        args['edited'] = upd.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        info.assert_any_call('Unpushing bodhi-2.0.0-2.fc17')
        info.assert_any_call('Removing f17-updates-testing-pending tag from bodhi-2.0.0-2.fc17')
        info.assert_any_call('Removing f17-updates-candidate tag from bodhi-2.0.0-2.fc17')
        tag_task.delay.assert_any_call(tag='f17-updates-signing-pending',
                                       builds=['bodhi-2.0.0-3.fc17'])
        tag_task.delay.assert_any_call(tag='f17-updates-candidate',
                                       builds=['bodhi-2.0.0-3.fc17'])
        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17

        Karma has been reset.
        """).strip()
        assert_multiline_equal(up['comments'][-1]['text'], comment)
        assert up['comments'][-3]['text'] == 'This update has been submitted for testing by guest. '
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-3.fc17'
        assert self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first() is None

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    @mock.patch('bodhi.server.models.tag_update_builds_task')
    @mock.patch('bodhi.server.models.Build.get_tags')
    @mock.patch('bodhi.server.models.log.info')
    def test_edit_testing_sidetag_update_with_new_builds(self, info, get_tags, tag_task, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.from_tag = 'f17-build-side-12345'
        upd.request = None
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        get_tags.return_value = ['f17-updates-testing',
                                 'f17-build-side-12345']

        args['edited'] = upd.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1,
                                    update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        info.assert_any_call('Unpushing bodhi-2.0.0-2.fc17')
        info.assert_any_call('Removing f17-updates-testing tag from bodhi-2.0.0-2.fc17')
        tag_task.delay.assert_any_call(tag='f17-updates-signing-pending',
                                       builds=['bodhi-2.0.0-3.fc17'])
        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'
        assert up['comments'][-1]['text'] == 'This update has been submitted for testing by guest. '
        comment = textwrap.dedent("""
        guest edited this update.

        New build(s):

        - bodhi-2.0.0-3.fc17

        Removed build(s):

        - bodhi-2.0.0-2.fc17

        Karma has been reset.
        """).strip()
        assert_multiline_equal(up['comments'][-2]['text'], comment)
        assert up['comments'][-4]['text'] == 'This update has been submitted for testing by guest. '
        assert len(up['builds']) == 1
        assert up['builds'][0]['nvr'] == 'bodhi-2.0.0-3.fc17'
        assert self.db.query(RpmBuild).filter_by(nvr='bodhi-2.0.0-2.fc17').first() is None

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    def test_edit_update_with_different_release(self, *args):
        """Test editing an update for one release with builds from another."""
        args = self.get_update('bodhi-2.0.0-2.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Add another release and package
        Release._tag_cache = None
        release = Release(
            name='F18', long_name='Fedora 18',
            id_prefix='FEDORA', version='18',
            dist_tag='f18', stable_tag='f18-updates',
            testing_tag='f18-updates-testing',
            candidate_tag='f18-updates-candidate',
            pending_signing_tag='f18-updates-testing-signing',
            pending_testing_tag='f18-updates-testing-pending',
            pending_stable_tag='f18-updates-pending',
            override_tag='f18-override',
            branch='f18',
            package_manager=PackageManager.unspecified,
            testing_repository=None)
        self.db.add(release)
        pkg = RpmPackage(name='nethack')
        self.db.add(pkg)
        self.db.commit()

        args = self.get_update('bodhi-2.0.0-2.fc17,nethack-4.0.0-1.fc18')
        args['edited'] = r.json['alias']
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body

        assert up['status'] == 'error'
        assert up['errors'][0]['description'] == 'Cannot add a F18 build to an F17 update'

    @mock.patch(**mock_valid_requirements)
    def test_edit_stable_update(self, *args):
        """Make sure we can't edit stable updates"""
        # First, create a testing update
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args, status=200)

        # Then, switch it to stable behind the scenes
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.stable

        # Then, try to edit it through the api again
        args['edited'] = up.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body
        assert up['status'] == 'error'
        assert up['errors'][0]['description'] == "Cannot edit stable updates"

    @mock.patch(**mock_valid_requirements)
    def test_edit_locked_update(self, *args):
        """Make sure some changes are prevented"""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args, status=200)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = True
        up.status = UpdateStatus.testing
        up.request = None
        up_id = up.id
        # Clear pending messages
        self.db.info['messages'] = []

        # Changing the notes should work
        args['edited'] = up.alias
        args['notes'] = 'Some new notes'

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            up = self.app.post_json('/updates/', args, status=200).json_body

        assert up['notes'] == 'Some new notes'

        # Changing the builds should fail
        args['notes'] = 'And yet some other notes'
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        r = self.app.post_json('/updates/', args, status=400).json_body
        assert r['status'] == 'error'
        assert 'errors' in r
        assert {'description': "Can't add builds to a locked update",
                'location': 'body', 'name': 'builds'} in r['errors']
        up = self.db.query(Update).get(up_id)
        assert up.notes == 'Some new notes'
        build = self.db.query(RpmBuild).filter_by(nvr=nvr).one()
        assert up.builds == [build]

    @mock.patch(**mock_valid_requirements)
    def test_pending_update_on_stable_karma_reached_autopush_enabled(self, *args):
        """Ensure that a pending update stays in testing if it hits stable karma while pending."""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.pending
        self.db.commit()

        up.comment(self.db, 'WFM', author='dustymabe', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        with fml_testing.mock_sends(api.Message, api.Message):
            up.comment(self.db, 'LGTM', author='bowlofeggs', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        assert up.karma == 2
        assert up.request == UpdateRequest.stable
        assert up.status == UpdateStatus.pending

    @mock.patch(**mock_valid_requirements)
    def test_pending_urgent_update_on_stable_karma_reached_autopush_enabled(self, *args):
        """
        Ensure that a pending urgent update directly requests for stable if
        it hits stable karma before reaching testing state.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2
        args['severity'] = 'urgent'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.pending
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        up.comment(self.db, 'WFM', author='dustymabe', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        with fml_testing.mock_sends(api.Message, api.Message):
            up.comment(self.db, 'LGTM', author='bowlofeggs', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        assert up.karma == 2
        assert up.request == UpdateRequest.stable
        assert up.status == UpdateStatus.pending

    @mock.patch(**mock_valid_requirements)
    def test_pending_update_on_stable_karma_not_reached(self, *args):
        """ Ensure that pending update does not directly request for stable
        if it does not hit stable karma before reaching testing state """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.pending
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        up.comment(self.db, 'WFM', author='dustymabe', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        assert up.karma == 1
        assert up.request == UpdateRequest.testing
        assert up.status == UpdateStatus.pending

    @mock.patch(**mock_valid_requirements)
    def test_pending_update_on_stable_karma_reached_autopush_disabled(self, *args):
        """ Ensure that pending update has option to request for stable directly
        if it hits stable karma before reaching testing state """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.pending
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        up.comment(self.db, 'WFM', author='dustymabe', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        up.comment(self.db, 'LGTM', author='bowlofeggs', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        assert up.karma == 2
        assert up.status == UpdateStatus.pending
        assert up.request == UpdateRequest.testing

        text = str(config.get('testing_approval_msg'))
        up.comment(self.db, text, author='bodhi')
        assert up.comments[-1]['text'] == (
            'This update can be pushed to stable now if the maintainer wishes'
        )

    @mock.patch(**mock_valid_requirements)
    def test_obsoletion_locked_with_open_request(self, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = True
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args).json_body

        assert r['request'] == 'testing'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.pending
        assert up.request == UpdateRequest.testing

    @mock.patch(**mock_valid_requirements)
    def test_obsoletion_unlocked_with_open_request(self, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args)

        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args).json_body

        assert r['request'] == 'testing'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.obsolete
        assert up.request is None

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_obsoletion_unlocked_with_open_stable_request(self, *args):
        """
        Ensure that we don't obsolete updates that have a stable request
        when we push a new update to testing, but we do when we submit
        the newer update to stable.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.request = UpdateRequest.stable
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        nvr_new = 'bodhi-2.0.0-3.fc17'
        args = self.get_update(nvr_new)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args).json_body

        assert r['request'] == 'testing'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.pending
        assert up.request == UpdateRequest.stable

        new_up = self.db.query(Build).filter_by(nvr=nvr_new).one().update
        new_up.status = UpdateStatus.testing
        new_up.request = None
        new_up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        new_up.date_testing = new_up.comments[-1].timestamp - timedelta(days=7)
        assert len(new_up.builds) == 1
        new_up.test_gating_status = TestGatingStatus.passed
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        assert new_up.days_in_testing == 7
        assert new_up.meets_testing_requirements is True

        with fml_testing.mock_sends(update_schemas.UpdateRequestStableV1):
            r = self.app.post_json(
                f'/updates/{new_up.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()}).json_body

        assert r['update']['request'] == 'stable'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.obsolete
        assert up.request is None

    @mock.patch(**mock_valid_requirements)
    def test_push_to_stable_for_obsolete_update(self, *args):
        """
        Obsolete update should not be submitted to testing
        Test Push to Stable option for obsolete update
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with mock.patch(**mock_uuid4_version1):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                self.app.post_json('/updates/', args)

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.testing
        up.request = None
        # Clear pending messages
        self.db.info['messages'] = []

        new_nvr = 'bodhi-2.0.0-3.fc17'
        args = self.get_update(new_nvr)
        with mock.patch(**mock_uuid4_version2):
            with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
                r = self.app.post_json('/updates/', args).json_body

        assert r['request'] == 'testing'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.status == UpdateStatus.obsolete
        expected_comment = 'This update has been obsoleted by [bodhi-2.0.0-3.fc17]({}).'
        expected_comment = expected_comment.format(
            urlparse.urljoin(config['base_address'],
                             '/updates/FEDORA-{}-53345602d5'.format(datetime.now().year)))
        assert up.comments[-1].text == expected_comment

        # Check Push to Stable button for obsolete update
        resp = self.app.get(f'/updates/{up.alias}',
                            headers={'Accept': 'text/html'})
        assert 'text/html' in resp.headers['Content-Type']
        assert up.builds[0].nvr in resp
        assert 'Push to Stable' not in resp

    @mock.patch(**mock_valid_requirements)
    def test_enabled_button_for_autopush(self, *args):
        """Test Enabled button on Update page when autopush is True"""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        with fml_testing.mock_sends(api.Message):
            resp = self.app.post_json('/updates/', args)

        resp = self.app.get(f"/updates/{resp.json['alias']}", headers={'Accept': 'text/html'})
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'The update will be automatically pushed to stable when karma reaches' in resp

    @mock.patch(**mock_valid_requirements)
    def test_disabled_button_for_autopush(self, *args):
        """Test Disabled button on Update page when autopush is False"""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        with fml_testing.mock_sends(api.Message):
            resp = self.app.post_json('/updates/', args)

        resp = self.app.get(f"/updates/{resp.json['alias']}", headers={'Accept': 'text/html'})
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'The update will not be automatically pushed to stable by karma' in resp

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_invalid_request(self, *args):
        """Test submitting an invalid request"""
        args = self.get_update()
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': 'foo', 'csrf_token': self.get_csrf_token()}, status=400)
        resp = resp.json_body
        request_vals = ", ".join(UpdateRequest.values())
        assert resp['status'] == 'error'
        assert resp['errors'][0]['description'] == f'"foo" is not one of {request_vals}'

        # Now try with None
        resp = self.app.post_json(
            '/updates/%s/request' % args['builds'],
            {'request': None, 'csrf_token': self.get_csrf_token()}, status=400)
        resp = resp.json_body
        assert resp['status'] == 'error'
        assert resp['errors'][0]['name'] == 'request'
        assert resp['errors'][0]['description'] == 'Required'

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_testing_request(self, *args):
        """Test submitting a valid testing request"""
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.locked = False
        args = self.get_update()
        args['request'] = None

        with fml_testing.mock_sends():
            resp = self.app.post_json(
                f'/updates/{update.alias}/request',
                {'request': 'testing', 'csrf_token': self.get_csrf_token()})

        assert resp.json['update']['request'] == 'testing'

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_revoke_action_for_stable_request(self, *args):
        """
        Test revoke action for stable request on testing update
        and check status after revoking the request
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = UpdateRequest.stable
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        with fml_testing.mock_sends(update_schemas.UpdateRequestRevokeV1):
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'revoke', 'csrf_token': self.get_csrf_token()})

        assert resp.json['update']['request'] is None
        assert resp.json['update']['status'] == 'testing'

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_revoke_action_for_testing_request(self, *args):
        """
        Test revoke action for testing request on pending update
        and check status after revoking the request
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        with fml_testing.mock_sends(update_schemas.UpdateRequestRevokeV1):
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'revoke', 'csrf_token': self.get_csrf_token()})

        assert resp.json['update']['request'] is None
        assert resp.json['update']['status'] == 'unpushed'

    @mock.patch(**mock_valid_requirements)
    def test_obsolete_if_unstable_with_autopush_enabled_when_pending(self, *args):
        """
        Send update to obsolete state if it reaches unstable karma on
        pending state where request is testing when Autopush is enabled. Make sure that it
        does not go to update-testing state.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 1
        args['unstable_karma'] = -1

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            response = self.app.post_json('/updates/', args)

        up = Update.get(response.json['alias'])
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.karma == -1
        assert up.status == UpdateStatus.obsolete
        assert up.request is None

    @mock.patch(**mock_valid_requirements)
    def test_obsolete_if_unstable_with_autopush_disabled_when_pending(self, *args):
        """
        Don't automatically send update to obsolete state if it reaches unstable karma on
        pending state when Autopush is disabled.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        args['unstable_karma'] = -1

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            response = self.app.post_json('/updates/', args)

        up = Update.get(response.json['alias'])
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.karma == -1
        assert up.status == UpdateStatus.pending
        assert up.request == UpdateRequest.testing

    @mock.patch(**mock_valid_requirements)
    def test_obsolete_if_unstable_karma_not_reached_with_autopush_enabled_when_pending(
            self, *args):
        """
        Don't send update to obsolete state if it does not reach unstable karma threshold
        on pending state when Autopush is enabled.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            response = self.app.post_json('/updates/', args)

        up = Update.get(response.json['alias'])
        up.status = UpdateStatus.pending
        up.request = UpdateRequest.testing
        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up.karma == -1
        assert up.status == UpdateStatus.pending
        assert up.request == UpdateRequest.testing

    @mock.patch(**mock_valid_requirements)
    def test_obsolete_if_unstable_with_autopush_enabled_when_testing(self, *args):
        """
        Send update to obsolete state if it reaches unstable karma threshold on
        testing state where request is stable when Autopush is enabled. Make sure that the
        autopush remains enabled and the update does not go to stable state.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            response = self.app.post_json('/updates/', args)

        up = Update.get(response.json['alias'])
        up.status = UpdateStatus.testing
        up.request = UpdateRequest.stable
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        up.comment(self.db, 'WFM', author='puiterwijk', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        up.comment(self.db, 'It has bug', author='bowlofeggs', karma=-1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        up.comment(self.db, 'Still not working', author='bob', karma=-1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update

        assert up.karma == -2
        assert up.autokarma is True
        assert up.status == UpdateStatus.obsolete
        assert up.request is None

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_request_after_unpush(self, *args):
        """Test request of this update after unpushing"""
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = UpdateRequest.stable
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        with fml_testing.mock_sends(update_schemas.UpdateCommentV1,
                                    update_schemas.UpdateRequestUnpushV1):
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'unpush', 'csrf_token': self.get_csrf_token()})

        assert resp.json['update']['request'] is None
        assert resp.json['update']['status'] == 'unpushed'

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_invalid_stable_request(self, *args):
        """
        Test submitting a stable request for an update that has yet to meet the stable requirements.
        """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.locked = False

        resp = self.app.post_json(
            f'/updates/{update.alias}/request',
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)
        assert resp.json['status'] == 'error'
        assert resp.json['errors'][0]['description'] == config.get('not_yet_tested_msg')

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_request_to_stable_based_on_stable_karma(self, *args):
        """
        Test request to stable before an update reaches stable karma
        and after it reaches stable karma when autokarma is disabled
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1
        with fml_testing.mock_sends(api.Message):
            response = self.app.post_json('/updates/', args)

        up = Update.get(response.json['alias'])
        up.status = UpdateStatus.testing
        up.request = None
        assert len(up.builds) == 1
        up.test_gating_status = TestGatingStatus.passed
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Checks failure for requesting to stable push before the update reaches stable karma
        up.comment(self.db, 'Not working', author='ralph', karma=0)

        with fml_testing.mock_sends(api.Message):
            self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()},
                status=400)

        up = Update.get(up.alias)
        assert up.request is None
        assert up.status == UpdateStatus.testing

        # Checks Success for requesting to stable push after the update reaches stable karma
        up.comment(self.db, 'LGTM', author='ralph', karma=1)

        with fml_testing.mock_sends(api.Message, api.Message):
            self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()},
                status=200)

        up = Update.get(up.alias)
        assert up.request == UpdateRequest.stable
        assert up.status == UpdateStatus.testing

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_stable_request_after_testing(self, *args):
        """
        Test submitting a stable request to an update that has met the minimum amount of time in
        testing.
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        assert len(up.builds) == 1
        up.test_gating_status = TestGatingStatus.passed
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        assert up.days_in_testing == 7
        assert up.meets_testing_requirements is True

        with fml_testing.mock_sends(update_schemas.UpdateRequestStableV1):
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()})

        assert resp.json['update']['request'] == 'stable'

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_request_to_archived_release(self, *args):
        """Test submitting a stable request to an update for an archived/EOL release.
        https://github.com/fedora-infra/bodhi/issues/725
        """
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.pending
        up.request = None
        up.release.state = ReleaseState.archived
        assert len(up.builds) == 1
        up.test_gating_status = TestGatingStatus.passed
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.post_json(
            f'/updates/{up.alias}/request',
            {'request': 'testing', 'csrf_token': self.get_csrf_token()},
            status=400)

        assert resp.json['status'] == 'error'
        assert resp.json['errors'][0]['description'] == (
            "cannot edit Update for an archived Release"
        )

    @mock.patch(**mock_failed_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_stable_request_failed_taskotron_results(self, *args):
        """Test submitting a stable request, but with bad taskotron results"""
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        assert len(up.builds) == 1
        up.test_gating_status = TestGatingStatus.passed
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        assert up.days_in_testing == 7
        assert up.meets_testing_requirements is True

        with fml_testing.mock_sends():
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()},
                status=400)

        assert 'errors' in resp
        assert 'Required task' in resp

    @mock.patch(**mock_absent_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_stable_request_absent_taskotron_results(self, *args):
        """Test submitting a stable request, but with absent task results"""
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=7)
        assert len(up.builds) == 1
        up.test_gating_status = TestGatingStatus.passed
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        assert up.days_in_testing == 7
        assert up.meets_testing_requirements is True

        with fml_testing.mock_sends():
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()},
                status=400)

        assert 'errors' in resp
        assert 'No result found for' in resp

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_stable_request_when_stable(self, *args):
        """Test submitting a stable request to an update that already been
        pushed to stable"""
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.stable
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=14)
        up.comment(self.db, 'This update has been pushed to stable', author='bodhi')
        assert len(up.builds) == 1
        up.test_gating_status = TestGatingStatus.passed
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        assert up.days_in_testing == 14
        assert up.meets_testing_requirements is True

        with fml_testing.mock_sends():
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()})

        assert resp.json['update']['status'] == 'stable'
        assert resp.json['update']['request'] is None

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_testing_request_when_testing(self, *args):
        """Test submitting a testing request to an update that already been
        pushed to testing"""
        args = self.get_update('bodhi-2.0.0-3.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.comment(self.db, 'This update has been pushed to testing', author='bodhi')
        up.date_testing = up.comments[-1].timestamp - timedelta(days=14)
        assert len(up.builds) == 1
        up.test_gating_status = TestGatingStatus.passed
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        assert up.days_in_testing == 14
        assert up.meets_testing_requirements is True

        with fml_testing.mock_sends():
            resp = self.app.post_json(
                f'/updates/{up.alias}/request',
                {'request': 'testing', 'csrf_token': self.get_csrf_token()})

        assert resp.json['update']['status'] == 'testing'
        assert resp.json['update']['request'] is None

    @mock.patch(**mock_valid_requirements)
    def test_update_with_older_build_in_testing_from_diff_user(self, r):
        """
        Test submitting an update for a package that has an older build within
        a multi-build update currently in testing submitted by a different
        maintainer.

        https://github.com/fedora-infra/bodhi/issues/78
        """
        title = 'bodhi-2.0-2.fc17 python-3.0-1.fc17'
        args = self.get_update(title)
        with fml_testing.mock_sends(api.Message):
            resp = self.app.post_json('/updates/', args)
        newuser = User(name='bob')
        self.db.add(newuser)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = None
        up.user = newuser
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        newtitle = 'bodhi-2.0-3.fc17'
        args = self.get_update(newtitle)
        with fml_testing.mock_sends(api.Message):
            resp = self.app.post_json('/updates/', args)

        # Note that this does **not** obsolete the other update
        assert len(resp.json_body['caveats']) == 2
        assert resp.json_body['caveats'][0]['description'] == (
            'The number of stable days required was set to the mandatory release value of 7 days'
        )
        assert resp.json_body['caveats'][1]['description'] == (
            "Please be aware that there is another update in flight owned by bob, containing "
            "bodhi-2.0-2.fc17. Are you coordinating with them?"
        )

        # Ensure the second update was created successfully
        self.db.query(Update).filter_by(alias=resp.json['alias']).one()

    @mock.patch(**mock_valid_requirements)
    def test_updateid_alias(self, *args):
        with fml_testing.mock_sends(api.Message):
            res = self.app.post_json('/updates/', self.get_update('bodhi-2.0.0-3.fc17'))
        json = res.json_body
        assert json['alias'] == json['updateid']

    def test_list_updates_by_lowercase_release_name(self):
        res = self.app.get('/updates/', {"releases": "f17"})
        body = res.json_body
        assert len(body['updates']) == 1

        up = body['updates'][0]
        assert up['title'] == 'bodhi-2.0-1.fc17'

    def test_redirect_to_package(self):
        "When you visit /updates/package, redirect to /updates/?packages=..."
        res = self.app.get('/updates/bodhi', status=302)
        target = 'http://localhost/updates/?packages=bodhi'
        assert res.headers['Location'] == target

        # But be sure that we don't redirect if the package doesn't exist
        res = self.app.get('/updates/nonexistent', status=404)

    def test_list_updates_by_alias_and_updateid(self):
        upd = self.db.query(Update).filter(Update.alias.isnot(None)).first()
        res = self.app.get('/updates/', {"alias": upd.alias})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        # We need to refetch the update since the call to /updates/ committed the transaction.
        upd = self.db.query(Update).filter(Update.alias.isnot(None)).first()
        assert up['title'] == upd.title
        assert up['alias'] == upd.alias

        res = self.app.get('/updates/', {"updateid": upd.alias})
        body = res.json_body
        assert len(body['updates']) == 1
        up = body['updates'][0]
        # We need to refetch the update since the call to /updates/ committed the transaction.
        upd = self.db.query(Update).filter(Update.alias.isnot(None)).first()
        assert up['title'] == upd.title

        res = self.app.get('/updates/', {"updateid": 'BLARG'})
        body = res.json_body
        assert not body['updates']

    @mock.patch(**mock_valid_requirements)
    def test_submitting_multi_release_updates(self, *args):
        """ https://github.com/fedora-infra/bodhi/issues/219 """
        # Add another release and package
        Release._tag_cache = None
        release = Release(
            name='F18', long_name='Fedora 18',
            id_prefix='FEDORA', version='18',
            dist_tag='f18', stable_tag='f18-updates',
            testing_tag='f18-updates-testing',
            candidate_tag='f18-updates-candidate',
            pending_signing_tag='f18-updates-testing-signing',
            pending_testing_tag='f18-updates-testing-pending',
            pending_stable_tag='f18-updates-pending',
            override_tag='f18-override',
            branch='f18',
            package_manager=PackageManager.unspecified,
            testing_repository=None)
        self.db.add(release)
        pkg = RpmPackage(name='nethack')
        self.db.add(pkg)
        self.db.commit()

        # A multi-release submission!!!  This should create *two* updates
        args = self.get_update('bodhi-2.0.0-2.fc17,bodhi-2.0.0-2.fc18')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1,
                                    update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        data = r.json_body

        assert 'caveats' in data
        assert len(data['caveats']) == 4
        assert data['caveats'][0]['description'] == (
            "Your update is being split into 2, one for each release."
        )
        assert data['caveats'][1]['description'] == (
            'The number of stable days required was set to the mandatory release value of 7 days'
        )
        assert data['caveats'][2]['description'] == (
            'The number of stable days required was set to the mandatory release value of 7 days'
        )
        assert data['caveats'][3]['description'] == (
            "This update has obsoleted bodhi-2.0-1.fc17, and has inherited its bugs and notes."
        )

        assert 'updates' in data
        assert len(data['updates']) == 2

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    def test_edit_update_bugs(self, *args):
        build = 'bodhi-2.0.0-2.fc17'
        args = self.get_update('bodhi-2.0.0-2.fc17')
        args['bugs'] = '56789'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # This has two bugs because it obsoleted another update and inherited its bugs.
        assert len(r.json['bugs']) == 2
        # Pretend it was pushed to testing and tested
        update = Build.query.filter_by(nvr=build).one().update
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Mark it as testing
        args['edited'] = update.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        args['bugs'] = '56789,98765'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1,
                                    update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body

        assert len(up['bugs']) == 2
        bug_ids = [bug['bug_id'] for bug in up['bugs']]
        assert 56789 in bug_ids
        assert 98765 in bug_ids
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'

        # now remove a bug
        args['edited'] = update.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'
        args['bugs'] = '98765'
        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert len(up['bugs']) == 1
        bug_ids = [bug['bug_id'] for bug in up['bugs']]
        assert 98765 in bug_ids
        assert up['status'] == 'pending'
        assert up['request'] == 'testing'

    @mock.patch(**mock_valid_requirements)
    def test_edit_missing_update(self, *args):
        """ Attempt to edit an update that doesn't exist """
        build = 'bodhi-2.0.0-2.fc17'
        edited = 'bodhi-1.0-1.fc17'
        args = self.get_update(build)
        args['edited'] = edited
        r = self.app.post_json('/updates/', args, status=400).json_body
        assert r['status'] == 'error'
        assert r['errors'][0]['description'] == 'Cannot find update to edit: %s' % edited

    @mock.patch(**mock_valid_requirements)
    def test_edit_update_and_disable_features(self, *args):
        build = 'bodhi-2.0.0-2.fc17'
        args = self.get_update('bodhi-2.0.0-2.fc17')

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['require_testcases'] is True
        assert up['require_bugs'] is False
        assert up['stable_karma'] == 3
        assert up['unstable_karma'] == -3

        # Pretend it was pushed to testing and tested
        update = Build.query.filter_by(nvr=build).one().update
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Mark it as testing
        args['edited'] = update.alias

        # Toggle a bunch of the booleans
        args['autokarma'] = False
        args['require_testcases'] = False
        args['require_bugs'] = True

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['status'] == 'testing'
        assert up['request'] is None

        assert up['require_bugs'] is True
        assert up['require_testcases'] is False
        assert up['stable_karma'] == 3
        assert up['unstable_karma'] == -3

    @mock.patch(**mock_valid_requirements)
    def test_edit_update_change_type(self, *args):
        build = 'bodhi-2.0.0-2.fc17'
        args = self.get_update('bodhi-2.0.0-2.fc17')
        args['type'] = 'newpackage'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['type'] == 'newpackage'

        # Pretend it was pushed to testing and tested
        update = Build.query.filter_by(nvr=build).one().update
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Mark it as testing
        args['edited'] = update.alias
        args['type'] = 'bugfix'

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['status'] == 'testing'
        assert up['request'] is None
        assert up['type'] == 'bugfix'

    def test_update_meeting_requirements_present(self):
        """ Check that the requirements boolean is present in our JSON """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        res = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'application/json'})

        actual = res.json_body['update']['meets_testing_requirements']
        expected = False
        assert actual == expected

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    def test_edit_testing_update_reset_karma(self, *args):
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing, tested and give it 2 karma
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = None
        upd.comment(self.db, 'LGTM', author='bob', karma=1)
        upd.comment(self.db, 'LGTM2ME2', author='other_bob', karma=1)
        assert upd.karma == 2
        # Clear pending messages
        self.db.info['messages'] = []

        # Then.. edit it and change the builds!
        args['edited'] = upd.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'

        with fml_testing.mock_sends(*[base_schemas.BodhiMessage] * 2):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        # This is what we really want to test here.
        assert up['karma'] == 0

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    def test_edit_testing_update_reset_karma_with_same_tester(self, *args):
        """
        Ensure that someone who gave an update karma can do it again after a reset.
        https://github.com/fedora-infra/bodhi/issues/659
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing and as tested
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = None
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Have bob +1 it
        upd.comment(self.db, 'LGTM', author='bob', karma=1)
        upd = Update.get(upd.alias)
        assert upd.karma == 1

        # Then.. edit it and change the builds!
        new_nvr = 'bodhi-2.0.0-3.fc17'
        args['edited'] = upd.alias
        args['builds'] = new_nvr
        with fml_testing.mock_sends(*[base_schemas.BodhiMessage] * 3):
            r = self.app.post_json('/updates/', args)
        up = r.json_body
        assert up['title'] == new_nvr
        # This is what we really want to test here.
        assert up['karma'] == 0

        # Have bob +1 it again
        upd = Update.get(upd.alias)
        upd.comment(self.db, 'Ship it!', author='bob', karma=1)

        # Bob should be able to give karma again since the reset
        assert upd.karma == 1

        # Then.. edit it and change the builds!
        newer_nvr = 'bodhi-2.0.0-4.fc17'
        args['edited'] = upd.alias
        args['builds'] = newer_nvr
        with fml_testing.mock_sends(*[base_schemas.BodhiMessage] * 2):
            r = self.app.post_json('/updates/', args)
        up = r.json_body
        assert up['title'] == newer_nvr
        # This is what we really want to test here.
        assert up['karma'] == 0

        # Have bob +1 it again
        upd = Update.get(upd.alias)
        upd.comment(self.db, 'Ship it!', author='bob', karma=1)

        # Bob should be able to give karma again since the reset
        assert upd.karma == 1

    @mock.patch(**mock_valid_requirements)
    def test__composite_karma_with_one_negative(self, *args):
        """The test asserts that _composite_karma returns (0, -1) when an update receives one
           negative karma"""
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args).json_body

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.request = None
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # The user gives negative karma first
        up.comment(self.db, 'Failed to work', author='luke', karma=-1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (0, -1)

    @mock.patch(**mock_valid_requirements)
    def test__composite_karma_with_changed_karma(self, *args):
        """
        This test asserts that _composite_karma returns (1, 0) when a user posts negative karma
        and then later posts positive karma.
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args).json_body

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.request = None
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # The user gives negative karma first
        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (0, -1)

        # The same user gives positive karma later
        up.comment(self.db, 'wfm', author='ralph', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (1, 0)
        assert up.karma == 1

    @mock.patch(**mock_valid_requirements)
    def test__composite_karma_with_positive_karma_first(self, *args):
        """
        This test asserts that _composite_karma returns (1, -1) when one user posts positive karma
        and then another user posts negative karma.
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args).json_body

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.request = None
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        #  user gives positive karma first
        up.comment(self.db, 'Works for me', author='ralph', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (1, 0)

        # Another user gives negative karma later
        up.comment(self.db, 'Failed to work', author='bowlofeggs', karma=-1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (1, -1)
        assert up.karma == 0

    @mock.patch(**mock_valid_requirements)
    def test__composite_karma_with_no_negative_karma(self, *args):
        """The test asserts that _composite_karma returns (*, 0) when there is no negative karma."""
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args).json_body

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.request = None
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        up.comment(self.db, 'LGTM', author='mac', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (1, 0)

        # Karma with no comment
        up.comment(self.db, ' ', author='bowlofeggs', karma=1)
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (2, 0)
        assert up.karma == 2

    @mock.patch(**mock_valid_requirements)
    def test__composite_karma_with_no_feedback(self, *args):
        """This test asserts that _composite_karma returns (0, 0) when an update has no feedback."""
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.1-1.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            self.app.post_json('/updates/', args).json_body

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.request = None
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        assert up._composite_karma == (0, 0)

    @mock.patch(**mock_valid_requirements)
    def test_karma_threshold_with_disabled_autopush(self, *args):
        """Ensure Karma threshold field is not None when Autopush is disabled."""
        build = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(build)
        args['autokarma'] = False
        args['stable_karma'] = 3
        args['unstable_karma'] = -3

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['autokarma'] is False
        assert up['stable_karma'] == 3
        assert up['unstable_karma'] == -3

        # Pretend it was pushed to testing
        update = Build.query.filter_by(nvr=build).one().update
        update.request = None
        update.status = UpdateStatus.testing
        update.pushed = True
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Mark it as testing
        args['edited'] = update.alias

        # Change Karma Thresholds
        args['stable_karma'] = 4
        args['unstable_karma'] = -4

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['status'] == 'testing'
        assert up['request'] is None
        assert up['autokarma'] is False
        assert up['stable_karma'] == 4
        assert up['unstable_karma'] == -4

    @mock.patch(**mock_valid_requirements)
    def test_disable_autopush_for_critical_updates(self, *args):
        """Make sure that autopush is disabled if a critical update receives any negative karma"""
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['critpath']
        assert resp.json['request'] == 'testing'
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        up.request = None
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # A user gives negative karma first
        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        # Another user gives positive karma
        up.comment(self.db, 'wfm', author='bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        assert up.karma == 0
        assert up.status == UpdateStatus.testing
        assert up.request is None

        # Autopush gets disabled since there is a negative karma from ralph
        assert up.autokarma is False

    @mock.patch(**mock_valid_requirements)
    def test_autopush_critical_update_with_no_negative_karma(self, *args):
        """Autopush critical update when it has no negative karma"""
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['critpath']
        assert resp.json['request'] == 'testing'
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        up.comment(self.db, 'LGTM', author='ralph', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        with fml_testing.mock_sends(api.Message, api.Message):
            up.comment(self.db, 'LGTM', author='bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        assert up.karma == 2

        # No negative karma: Update gets automatically marked as stable
        assert up.autokarma is True

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        assert up.request == UpdateRequest.stable

    @mock.patch(**mock_valid_requirements)
    def test_manually_push_critical_update_with_negative_karma(self, *args):
        """
        Manually push critical update when it has negative karma
        Autopush gets disabled after it receives negative karma
        A user gives negative karma, but another 3 users give positive karma
        The critical update should be manually pushed because of the negative karma
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 3
        args['unstable_karma'] = -3

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['critpath']
        assert resp.json['request'] == 'testing'

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'LGTM', author='bowlofeggs', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'wfm', author='luke', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'LGTM', author='puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'LGTM', author='trishnag', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        assert up.karma == 3
        assert up.autokarma is False
        # The request should still be at testing. This assertion tests for
        # https://github.com/fedora-infra/bodhi/issues/989 where karma comments were resetting the
        # request to None.
        assert up.request == UpdateRequest.testing
        assert up.status == UpdateStatus.testing
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{up.alias}',
                            headers={'Accept': 'text/html'})
        assert 'text/html' in resp.headers['Content-Type']
        assert 'kernel-3.11.5-300.fc17' in resp

    @mock.patch(**mock_valid_requirements)
    def test_manually_push_critical_update_with_autopush_turned_off(self, *args):
        """
        Manually push critical update when it has Autopush turned off
        and make sure the update doesn't get Autopushed
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'kernel-3.11.5-300.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 3
        args['unstable_karma'] = -3

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['critpath']
        assert resp.json['request'] == 'testing'
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        up.comment(self.db, 'LGTM Now', author='ralph', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'wfm', author='luke', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'LGTM', author='puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        assert up.karma == 3
        assert up.autokarma is False
        # The request should still be at testing. This assertion tests for
        # https://github.com/fedora-infra/bodhi/issues/989 where karma comments were resetting the
        # request to None.
        assert up.request == UpdateRequest.testing
        assert up.status == UpdateStatus.testing
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{up.alias}',
                            headers={'Accept': 'text/html'})
        assert 'text/html' in resp.headers['Content-Type']
        assert 'kernel-3.11.5-300.fc17' in resp

    @mock.patch(**mock_valid_requirements)
    def test_disable_autopush_non_critical_update_with_negative_karma(self, *args):
        """Disable autokarma on non-critical updates upon negative comment."""
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 3
        args['unstable_karma'] = -3

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['request'] == 'testing'
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        up.comment(self.db, 'Failed to work', author='ralph', karma=-1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        expected_comment = config.get('disable_automatic_push_to_stable')
        assert up.comments[3].text == expected_comment

        up.comment(self.db, 'LGTM Now', author='ralph', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'wfm', author='luke', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        up.comment(self.db, 'LGTM', author='puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        assert up.karma == 3
        assert up.autokarma is False

        # Request and Status remains testing since the autopush is disabled
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        assert up.request == UpdateRequest.testing
        assert up.status == UpdateStatus.testing

    @mock.patch(**mock_valid_requirements)
    def test_autopush_non_critical_update_with_no_negative_karma(self, *args):
        """
        Make sure autopush doesn't get disabled for Non Critical update if it
        does not receive any negative karma. Test update gets automatically
        marked as stable.
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = True
        args['stable_karma'] = 2
        args['unstable_karma'] = -2

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        assert resp.json['request'] == 'testing'
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        up.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        up.comment(self.db, 'LGTM Now', author='ralph', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        with fml_testing.mock_sends(api.Message, api.Message):
            up.comment(self.db, 'WFM', author='puiterwijk', karma=1)
        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()

        # No negative karma: Update gets automatically marked as stable
        assert up.autokarma is True

        up = self.db.query(Update).filter_by(alias=resp.json['alias']).one()
        assert up.request == UpdateRequest.stable

    @mock.patch(**mock_valid_requirements)
    def test_edit_button_not_present_when_stable(self, *args):
        """
        Assert that the edit button is not present on stable updates.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)
        update = Update.get(resp.json['alias'])
        update.date_stable = datetime.utcnow()
        update.status = UpdateStatus.stable
        update.pushed = True
        self.db.commit()

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks Edit text not in the html page for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'Push to Stable' not in resp
        assert '<span class="fa fa-fw fa-pencil-square-o"></span> Edit' not in resp

    @mock.patch.dict('bodhi.server.models.config', {'test_gating.required': True})
    @mock.patch('bodhi.server.models.Update.update_test_gating_status')
    def test_push_to_stable_button_not_present_when_test_gating_status_failed(self, update_tg):
        """The push to stable button should not appear if the test_gating_status is failed."""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['requirements'] = ''
        update_tg.return_value = TestGatingStatus.failed

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args, headers={'Accept': 'application/json'})

        update = Update.get(resp.json['alias'])
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.failed
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        self.registry.settings['test_gating.required'] = True

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        assert 'Push to Stable' not in resp
        assert 'Edit' in resp

    @mock.patch.dict('bodhi.server.models.config', {'test_gating.required': True})
    @mock.patch('bodhi.server.models.Update.update_test_gating_status')
    def test_push_to_stable_button_present_when_test_gating_status_passed(self, update_tg):
        """The push to stable button should appear if the test_gating_status is passed."""
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['requirements'] = ''
        update_tg.return_value = TestGatingStatus.passed

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args, headers={'Accept': 'application/json'})

        update = Update.get(resp.json['alias'])
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.passed
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []
        self.registry.settings['test_gating.required'] = True

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        assert 'Push to Stable' in resp
        assert 'Edit' in resp

    @mock.patch(**mock_valid_requirements)
    def test_push_to_stable_button_present_when_karma_reached(self, *args):
        """
        Assert that the "Push to Stable" button appears when the required karma is
        reached.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        update = Update.get(resp.json['alias'])
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'Push to Stable' in resp
        assert 'Edit' in resp

    @mock.patch(**mock_valid_requirements)
    def test_push_to_stable_button_present_when_karma_reached_urgent(self, *args):
        """
        Assert that the "Push to Stable" button appears when the required karma is
        reached for an urgent update.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        update = Update.get(resp.json['alias'])
        update.severity = UpdateSeverity.urgent
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.autokarma = False
        update.stable_karma = 1
        update.comment(self.db, 'works', 1, 'bowlofeggs')
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'Push to Stable' in resp
        assert 'Edit' in resp

    @mock.patch(**mock_valid_requirements)
    def test_push_to_stable_button_present_when_time_reached(self, *args):
        """
        Assert that the "Push to Stable" button appears when the required time in testing is
        reached.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        update = Update.get(resp.json['alias'])
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        # This update has been in testing a while, so a "Push to Stable" button should appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'Push to Stable' in resp
        assert 'Edit' in resp

    @mock.patch(**mock_valid_requirements)
    def test_push_to_stable_button_present_when_time_reached_and_urgent(self, *args):
        """
        Assert that the "Push to Stable" button appears when the required time in testing is
        reached.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        update = Update.get(resp.json['alias'])
        update.severity = UpdateSeverity.urgent
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        # This urgent update has been in testing a while, so a "Push to Stable" button should
        # appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'Push to Stable' in resp
        assert 'Edit' in resp

    @mock.patch(**mock_valid_requirements)
    def test_push_to_stable_button_present_when_time_reached_critpath(self, *args):
        """
        Assert that the "Push to Stable" button appears when it should for a critpath update.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        update = Update.get(resp.json['alias'])
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.critpath = True
        # This update has been in testing a while, so a "Push to Stable" button should appear.
        update.date_testing = datetime.now() - timedelta(days=30)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks Push to Stable text in the html page for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert 'Push to Stable' in resp
        assert 'Edit' in resp

    def assert_severity_html(self, severity, text=()):
        """
        Assert that the "Update Severity" label appears correctly given specific 'severity'.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        update = Update.get(resp.json['alias'])
        update.severity = severity
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.date_testing = datetime.now() - timedelta(days=30)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks correct class label and text for update severity in the html page for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        for s in text:
            assert s in resp

    @mock.patch(**mock_valid_requirements)
    def test_update_severity_label_present_correctly_when_severity_is_urgent(self, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is urgent.
        """
        self.assert_severity_html(
            UpdateSeverity.urgent,
            ['<div class="col font-weight-bold text-muted">Severity', 'urgent']
        )

    @mock.patch(**mock_valid_requirements)
    def test_update_severity_label_present_correctly_when_severity_is_high(self, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is high.
        """
        self.assert_severity_html(
            UpdateSeverity.high,
            ['<div class="col font-weight-bold text-muted">Severity', 'high']
        )

    @mock.patch(**mock_valid_requirements)
    def test_update_severity_label_present_correctly_when_severity_is_medium(self, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is medium.
        """
        self.assert_severity_html(
            UpdateSeverity.medium,
            ['<div class="col font-weight-bold text-muted">Severity', 'medium']
        )

    @mock.patch(**mock_valid_requirements)
    def test_update_severity_label_present_correctly_when_severity_is_low(self, *args):
        """
        Assert that the "Update Severity" label appears correctly when the severity is low.
        """
        self.assert_severity_html(
            UpdateSeverity.low,
            ['<div class="col font-weight-bold text-muted">Severity', 'low']
        )

    @mock.patch(**mock_valid_requirements)
    def test_update_severity_label_absent_when_severity_is_None(self, *args):
        """
        Assert that the "Update Severity" label doesn't appear when severity is None
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        update = Update.get(resp.json['alias'])
        update.severity = None
        update.status = UpdateStatus.testing
        update.request = None
        update.pushed = True
        update.date_testing = datetime.now() - timedelta(days=30)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        resp = self.app.get(f'/updates/{update.alias}', headers={'Accept': 'text/html'})

        # Checks 'Update Severity' text is absent in the html for this update
        assert 'text/html' in resp.headers['Content-Type']
        assert nvr in resp
        assert '<strong>Update Severity</strong>' not in resp

    @mock.patch(**mock_valid_requirements)
    def test_manually_push_to_stable_based_on_karma_request_none(self, *args):
        """
        Test manually push to stable when autokarma is disabled
        and karma threshold is reached

        This test starts the update with request None.
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        # Makes autokarma disabled
        # Sets stable karma to 1
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        # Marks it as no request
        upd = Update.get(resp.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = None
        upd.pushed = True
        upd.date_testing = datetime.now() - timedelta(days=1)
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Checks karma threshold is reached
        # Makes sure stable karma is not None
        # Ensures Request doesn't get set to stable automatically since autokarma is disabled
        upd.comment(self.db, 'LGTM', author='ralph', karma=1)
        upd = Update.get(upd.alias)
        assert upd.karma == 1
        assert upd.stable_karma == 1
        assert upd.status == UpdateStatus.testing
        assert upd.request is None
        assert upd.autokarma is False
        assert upd.pushed is True

        text = str(config.get('testing_approval_msg'))
        upd.comment(self.db, text, author='bodhi')
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        # Checks Push to Stable text in the html page for this update
        resp = self.app.get(f'/updates/{upd.alias}',
                            headers={'Accept': 'text/html'})
        assert 'text/html' in resp.headers['Content-Type']
        assert upd.builds[0].nvr in resp
        assert 'Push to Stable' in resp

    @mock.patch(**mock_valid_requirements)
    def test_manually_push_to_stable_based_on_karma_request_testing(self, *args):
        """
        Test manually push to stable when autokarma is disabled
        and karma threshold is reached. Ensure that the option/button to push to
        stable is not present prior to entering the stable request state.

        This test starts the update with request testing.
        """

        # Disabled
        # Sets stable karma to 1
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)
        args['autokarma'] = False
        args['stable_karma'] = 1

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            resp = self.app.post_json('/updates/', args)

        # Marks it as testing
        upd = Update.get(resp.json['alias'])
        upd.status = UpdateStatus.testing
        upd.pushed = True
        upd.request = None
        upd.date_testing = datetime.now() - timedelta(days=1)
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Checks karma threshold is reached
        # Makes sure stable karma is not None
        # Ensures Request doesn't get set to stable automatically since autokarma is disabled
        upd.comment(self.db, 'LGTM', author='ralph', karma=1)
        upd = Update.get(upd.alias)
        assert upd.karma == 1
        assert upd.stable_karma == 1
        assert upd.status == UpdateStatus.testing
        assert upd.request is None
        assert upd.autokarma is False

        text = str(config.get('testing_approval_msg'))
        upd.comment(self.db, text, author='bodhi')
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        # Checks Push to Stable text in the html page for this update
        resp = self.app.get(f'/updates/{upd.alias}',
                            headers={'Accept': 'text/html'})
        assert 'text/html' in resp.headers['Content-Type']
        assert upd.builds[0].nvr in resp
        assert 'Push to Stable' in resp

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    def test_edit_update_with_expired_override(self, *args):
        """
        """
        user = User(name='bob')
        self.db.add(user)
        self.db.commit()

        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Create a new expired override
        upd = Update.get(r.json['alias'])
        override = BuildrootOverride(
            build=upd.builds[0], submitter=user, notes='testing',
            expiration_date=datetime.utcnow(), expired_date=datetime.utcnow())
        self.db.add(override)
        self.db.commit()

        # Edit it and change the builds
        new_nvr = 'bodhi-2.0.0-3.fc17'
        args['edited'] = upd.alias
        args['builds'] = new_nvr

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['title'] == new_nvr

        # Change it back to ensure we can still reference the older build
        args['edited'] = upd.alias
        args['builds'] = nvr

        with fml_testing.mock_sends(update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body
        assert up['title'] == nvr

    @mock.patch(**mock_taskotron_results)
    @mock.patch(**mock_valid_requirements)
    def test_submit_older_build_to_stable(self, *args):
        """
        Ensure we cannot submit an older build to stable when a newer one
        already exists there.
        """
        update = self.db.query(Update).one()
        update.status = UpdateStatus.stable
        update.request = None
        self.db.commit()

        oldbuild = 'bodhi-1.0-1.fc17'

        # Create a newer build
        build = RpmBuild(nvr=oldbuild, package=update.builds[0].package)
        self.db.add(build)
        update = Update(builds=[build], type=UpdateType.bugfix,
                        request=UpdateRequest.testing, notes='second update',
                        user=update.user, release=update.release,
                        stable_karma=3, unstable_karma=-3)
        update.comment(self.db, "foo1", 1, 'foo1')
        update.comment(self.db, "foo2", 1, 'foo2')
        with fml_testing.mock_sends(api.Message, api.Message, api.Message):
            update.comment(self.db, "foo3", 1, 'foo3')
        self.db.add(update)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        # Try and submit an older build to stable
        resp = self.app.post_json(
            f'/updates/{update.alias}/request',
            {'request': 'stable', 'csrf_token': self.get_csrf_token()},
            status=400)

        assert resp.json['status'] == 'error'
        assert resp.json['errors'][0]['description'] == (
            "Cannot submit bodhi ('0', '1.0', '1.fc17') to stable since it is older than "
            "('0', '2.0', '1.fc17')"
        )

        # see if we get the error message rpm.labelcompare succeeds
        with mock.patch('rpm.labelCompare') as rpm_label_compare:
            rpm_label_compare.return_value = 0
            resp = self.app.post_json(
                f'/updates/{update.alias}/request',
                {'request': 'stable', 'csrf_token': self.get_csrf_token()},
                status=200)

    @mock.patch(**mock_valid_requirements)
    def test_edit_testing_update_with_build_from_different_update(self, *args):
        """
        https://github.com/fedora-infra/bodhi/issues/803
        """
        # Create an update with a build that we will try and add to another update
        nvr1 = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr1)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = None
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Create an update for a different build
        nvr2 = 'koji-2.0.0-1.fc17'
        args = self.get_update(nvr2)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        # Mark it as testing
        upd = Update.get(r.json['alias'])
        upd.status = UpdateStatus.testing
        upd.request = None
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # Edit the nvr2 update and add nvr1
        args['edited'] = upd.alias
        args['builds'] = '%s,%s' % (nvr1, nvr2)
        r = self.app.post_json('/updates/', args, status=400)
        up = r.json_body
        assert up['status'] == 'error'
        assert up['errors'][0]['description'] == 'Update for bodhi-2.0.0-2.fc17 already exists'

        up = Update.get(upd.alias)
        assert up.title == nvr2  # nvr1 shouldn't be able to be added
        assert up.status == UpdateStatus.testing
        assert len(up.builds) == 1
        assert up.builds[0].nvr == nvr2

        # nvr1 update should remain intact
        up = Build.query.filter_by(nvr=nvr1).one().update
        assert up.title == nvr1
        assert up.status == UpdateStatus.testing
        assert len(up.builds) == 1
        assert up.builds[0].nvr == nvr1

    @mock.patch('bodhi.server.services.updates.handle_side_and_related_tags_task', mock.Mock())
    @mock.patch('bodhi.server.models.tag_update_builds_task', mock.Mock())
    @mock.patch(**mock_valid_requirements)
    def test_meets_testing_requirements_since_karma_reset_critpath(self, *args):
        """
        Ensure a critpath update still meets testing requirements after receiving negative karma
        and after a karma reset event.
        """
        nvr = 'bodhi-2.0.0-2.fc17'
        args = self.get_update(nvr)

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1):
            r = self.app.post_json('/updates/', args)

        update = Update.get(r.json['alias'])
        update.status = UpdateStatus.testing
        update.request = None
        update.critpath = True
        update.autokarma = True
        update.date_testing = datetime.utcnow() + timedelta(days=-20)
        update.comment(self.db, 'lgtm', author='friend', karma=1)
        update.comment(self.db, 'lgtm', author='friend2', karma=1)
        update.comment(self.db, 'bad', author='enemy', karma=-1)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        assert update.meets_testing_requirements is False

        args['edited'] = update.alias
        args['builds'] = 'bodhi-2.0.0-3.fc17'

        with fml_testing.mock_sends(update_schemas.UpdateRequestTestingV1,
                                    update_schemas.UpdateEditV1):
            r = self.app.post_json('/updates/', args)

        up = r.json_body

        assert up['title'] == 'bodhi-2.0.0-3.fc17'
        assert up['karma'] == 0
        assert up['date_testing'] == None
        update = Update.get(update.alias)
        update.status = UpdateStatus.testing
        self.date_testing = datetime.utcnow() + timedelta(days=7)
        update.comment(self.db, 'lgtm', author='friend3', karma=1)
        update.comment(self.db, 'lgtm2', author='friend4', karma=1)
        # Let's clear any messages that might get sent
        self.db.info['messages'] = []

        assert update.days_to_stable == 0
        assert update.meets_testing_requirements is True


class TestWaiveTestResults(BasePyTestCase):
    """
    This class contains tests for the waive_test_results() function.
    """
    def test_cannot_waive_test_results_on_locked_update(self, *args):
        """Ensure that we get an error if trying to waive test results of a locked update"""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed
        up.locked = True

        post_data = dict(update=nvr,
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            "Can't waive test results on a locked update"
        )
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should not have been altered.
        assert up.test_gating_status == TestGatingStatus.failed

    def test_cannot_waive_test_results_when_test_gating_is_off(self, *args):
        """
        Ensure that we get an error if trying to waive test results of an update
        when test gating is off.
        """
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed
        up.locked = False

        post_data = dict(update=nvr,
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == "Test gating is not enabled"
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should not have been altered.
        assert up.test_gating_status == TestGatingStatus.failed

    @mock.patch('bodhi.server.services.updates.Update.waive_test_results',
                side_effect=LockedUpdateException('LockedUpdateException. oops!'))
    @mock.patch('bodhi.server.services.updates.log.warning')
    def test_LockedUpdateException_exception(self, log_warning, waive_test_results, *args):
        """Ensure that an LockedUpdateException Exception is handled by waive_test_results()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed
        up.locked = False

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'LockedUpdateException. oops!'
        log_warning.assert_called_once_with('LockedUpdateException. oops!')
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should not have been altered.
        assert up.test_gating_status == TestGatingStatus.failed

    @mock.patch('bodhi.server.services.updates.Update.waive_test_results',
                side_effect=BodhiException('BodhiException. oops!'))
    @mock.patch('bodhi.server.services.updates.log.error')
    def test_BodhiException_exception(self, log_error, waive_test_results, *args):
        """Ensure that an BodhiException Exception is handled by waive_test_results()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed
        up.locked = False
        post_data = dict(update=up.alias, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f"/updates/{post_data['update']}/waive-test-results", post_data,
                                 status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'BodhiException. oops!'
        log_error.assert_called_once()
        assert log_error.call_args_list[0][0][0] == "Failed to waive the test results: %s"
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should not have been altered.
        assert up.test_gating_status == TestGatingStatus.failed

    @mock.patch('bodhi.server.services.updates.Update.waive_test_results',
                side_effect=IOError('IOError. oops!'))
    @mock.patch('bodhi.server.services.updates.log.exception')
    def test_unexpected_exception(self, log_exception, waive_test_results, *args):
        """Ensure that an unexpected Exception is handled by waive_test_results()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed
        up.locked = False

        post_data = dict(update=nvr, request='stable',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'IOError. oops!'
        log_exception.assert_called_once_with("Unhandled exception in waive_test_results")
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should not have been altered.
        assert up.test_gating_status == TestGatingStatus.failed

    @mock.patch.dict(config, [('test_gating.required', True)])
    @mock.patch('bodhi.server.util.waiverdb_api_post')
    @mock.patch('bodhi.server.util.greenwave_api_post')
    @mock.patch('bodhi.server.models.User.openid', mock.MagicMock(return_value=None))
    @mock.patch('bodhi.server.models.User.avatar', mock.MagicMock(return_value=None))
    def test_waive_test_results_1_unsatisfied_requirement(
            self, greenwave_api_post, waiverdb_api_post, *args):
        """Ensure that waiverdb and greenwaved are properly called when greenwave returns only one
        unsatisfied requirements."""
        nvr = 'bodhi-2.0-1.fc17'
        greenwave_api_post.return_value = {
            'unsatisfied_requirements': [
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'dist.rpmdeplint',
                    'type': 'test-result-failed'
                }
            ],
        }

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed

        post_data = dict(update=nvr, comment="This is expected", csrf_token=self.get_csrf_token())

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=200)

        greenwave_api_post.assert_called_once_with(
            'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision',
            {
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': up.alias, 'type': 'bodhi_update'}
                ],
                'verbose': False,
            }
        )

        waiverdb_api_post.assert_called_once_with(
            'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0/waivers/',
            {
                'username': 'guest',
                'comment': 'This is expected',
                'waived': True,
                'product_version': 'fedora-17',
                'testcase': 'dist.rpmdeplint',
                'subject': {
                    'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'
                }
            }
        )

        assert list(res.json_body.keys()) == ['update']
        assert res.json_body['update'] == up.__json__()
        assert res.json_body['update']['test_gating_status'] == 'waiting'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should have been reset to waiting.
        assert up.test_gating_status == TestGatingStatus.waiting
        # Check for the comment multiple ways
        expected_comment = "This update's test gating status has been changed to 'waiting'."
        assert res.json_body["update"]['comments'][-1]['text'] == expected_comment
        assert up.comments[-1].text == expected_comment

    @mock.patch.dict(config, [('test_gating.required', True)])
    @mock.patch('bodhi.server.util.waiverdb_api_post')
    @mock.patch('bodhi.server.util.greenwave_api_post')
    @mock.patch('bodhi.server.models.User.openid', mock.MagicMock(return_value=None))
    @mock.patch('bodhi.server.models.User.avatar', mock.MagicMock(return_value=None))
    def test_waive_test_results_2_unsatisfied_requirements(
            self, greenwave_api_post, waiverdb_api_post, *args):
        """Ensure that waiverdb and greenwaved are properly called when greenwave returns two
        unsatisfied requirements."""
        nvr = 'bodhi-2.0-1.fc17'
        greenwave_api_post.return_value = {
            'unsatisfied_requirements': [
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'dist.rpmdeplint',
                    'type': 'test-result-failed'
                },
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'atomic_ci_pipeline_results',
                    'type': 'test-result-failed'
                }
            ],
        }

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed

        post_data = dict(update=nvr, csrf_token=self.get_csrf_token())

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=200)

        greenwave_api_post.assert_called_once_with(
            'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision',
            {
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': up.alias, 'type': 'bodhi_update'}
                ],
                'verbose': False,
            }
        )

        calls = [
            mock.call(
                'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0/waivers/',
                {
                    'username': 'guest',
                    'comment': None,
                    'waived': True,
                    'product_version': 'fedora-17',
                    'testcase': 'dist.rpmdeplint',
                    'subject': {
                        'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'
                    }
                }
            ),
            mock.call(
                'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0/waivers/',
                {
                    'username': 'guest',
                    'comment': None,
                    'waived': True,
                    'product_version': 'fedora-17',
                    'testcase': 'atomic_ci_pipeline_results',
                    'subject': {
                        'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'
                    }
                }
            )
        ]
        assert waiverdb_api_post.mock_calls == calls

        assert list(res.json_body.keys()) == ['update']
        assert res.json_body['update'] == up.__json__()
        assert res.json_body['update']['test_gating_status'] == 'waiting'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should have been reset to waiting.
        assert up.test_gating_status == TestGatingStatus.waiting
        # Check for the comment multiple ways
        expected_comment = "This update's test gating status has been changed to 'waiting'."
        assert res.json_body["update"]['comments'][-1]['text'] == expected_comment
        assert up.comments[-1].text == expected_comment

    @mock.patch.dict(config, [('test_gating.required', True)])
    @mock.patch('bodhi.server.util.waiverdb_api_post')
    @mock.patch('bodhi.server.util.greenwave_api_post')
    @mock.patch('bodhi.server.models.User.openid', mock.MagicMock(return_value=None))
    @mock.patch('bodhi.server.models.User.avatar', mock.MagicMock(return_value=None))
    def test_waive_test_results_1_of_2_unsatisfied_requirements(
            self, greenwave_api_post, waiverdb_api_post, *args):
        """Ensure that waiverdb and greenwaved are properly called when greenwave returns only two
        unsatisfied requirements but only one of them is waived."""
        nvr = 'bodhi-2.0-1.fc17'
        greenwave_api_post.return_value = {
            'unsatisfied_requirements': [
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'dist.rpmdeplint',
                    'type': 'test-result-failed'
                },
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'atomic_ci_pipeline_results',
                    'type': 'test-result-failed'
                }
            ],
        }

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed

        post_data = dict(
            update=nvr,
            tests="atomic_ci_pipeline_results",
            csrf_token=self.get_csrf_token()
        )

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=200)

        greenwave_api_post.assert_called_once_with(
            'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision',
            {
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': up.alias, 'type': 'bodhi_update'}
                ],
                'verbose': False,
            }
        )

        waiverdb_api_post.assert_called_once_with(
            'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0/waivers/',
            {
                'username': 'guest',
                'comment': None,
                'waived': True,
                'product_version': 'fedora-17',
                'testcase': 'atomic_ci_pipeline_results',
                'subject': {
                    'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'
                }
            }
        )

        assert list(res.json_body.keys()) == ['update']
        assert res.json_body['update'] == up.__json__()
        assert res.json_body['update']['test_gating_status'] == 'waiting'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should have been reset to waiting.
        assert up.test_gating_status == TestGatingStatus.waiting
        # Check for the comment multiple ways
        expected_comment = "This update's test gating status has been changed to 'waiting'."
        assert res.json_body["update"]['comments'][-1]['text'] == expected_comment
        assert up.comments[-1].text == expected_comment

    @mock.patch.dict(config, [('test_gating.required', True)])
    @mock.patch('bodhi.server.util.waiverdb_api_post')
    @mock.patch('bodhi.server.util.greenwave_api_post')
    @mock.patch('bodhi.server.models.User.openid', mock.MagicMock(return_value=None))
    @mock.patch('bodhi.server.models.User.avatar', mock.MagicMock(return_value=None))
    def test_waive_test_results_2_of_2_unsatisfied_requirements(
            self, greenwave_api_post, waiverdb_api_post, *args):
        """Ensure that waiverdb and greenwaved are properly called when greenwave returns only two
        unsatisfied requirements and both of them are waived."""
        nvr = 'bodhi-2.0-1.fc17'
        greenwave_api_post.return_value = {
            'unsatisfied_requirements': [
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'dist.rpmdeplint',
                    'type': 'test-result-failed'
                },
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'atomic_ci_pipeline_results',
                    'type': 'test-result-failed'
                }
            ],
        }

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed

        post_data = dict(
            update=nvr,
            tests=["atomic_ci_pipeline_results", "dist.rpmdeplint"],
            csrf_token=self.get_csrf_token()
        )

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=200)

        greenwave_api_post.assert_called_once_with(
            'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision',
            {
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': up.alias, 'type': 'bodhi_update'}
                ],
                'verbose': False,
            }
        )

        calls = [
            mock.call(
                'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0/waivers/',
                {
                    'username': 'guest',
                    'comment': None,
                    'waived': True,
                    'product_version': 'fedora-17',
                    'testcase': 'dist.rpmdeplint',
                    'subject': {
                        'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'
                    }
                }
            ),
            mock.call(
                'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0/waivers/',
                {
                    'username': 'guest',
                    'comment': None,
                    'waived': True,
                    'product_version': 'fedora-17',
                    'testcase': 'atomic_ci_pipeline_results',
                    'subject': {
                        'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'
                    }
                }
            )
        ]
        assert waiverdb_api_post.mock_calls == calls

        assert list(res.json_body.keys()) == ['update']
        assert res.json_body['update'] == up.__json__()
        assert res.json_body['update']['test_gating_status'] == 'waiting'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should have been updated to waiting.
        assert up.test_gating_status == TestGatingStatus.waiting
        # Check for the comment multiple ways
        expected_comment = "This update's test gating status has been changed to 'waiting'."
        assert res.json_body["update"]['comments'][-1]['text'] == expected_comment
        assert up.comments[-1].text == expected_comment

    @mock.patch.dict(config, [('test_gating.required', True)])
    @mock.patch('bodhi.server.util.waiverdb_api_post')
    @mock.patch('bodhi.server.util.greenwave_api_post')
    @mock.patch('bodhi.server.models.User.openid', mock.MagicMock(return_value=None))
    @mock.patch('bodhi.server.models.User.avatar', mock.MagicMock(return_value=None))
    def test_waive_test_results_unfailing_tests(
            self, greenwave_api_post, waiverdb_api_post, *args):
        """Ensure that waiverdb and greenwaved are properly called when greenwave returns only two
        unsatisfied requirements and one of the two asked to be waived isn't a requirement."""
        nvr = 'bodhi-2.0-1.fc17'
        greenwave_api_post.return_value = {
            'unsatisfied_requirements': [
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'dist.rpmdeplint',
                    'type': 'test-result-failed'
                },
                {
                    'item': {
                        'item': 'bodhi-2.0-1.fc17',
                        'type': 'koji_build'
                    },
                    'scenario': None,
                    'testcase': 'atomic_ci_pipeline_results',
                    'type': 'test-result-failed'
                }
            ],
        }

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.test_gating_status = TestGatingStatus.failed

        post_data = dict(
            update=nvr,
            tests=["generic_ci_pipeline_results", "dist.rpmdeplint"],
            csrf_token=self.get_csrf_token()
        )

        res = self.app.post_json(f'/updates/{up.alias}/waive-test-results', post_data, status=200)

        greenwave_api_post.assert_called_once_with(
            'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision',
            {
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': up.alias, 'type': 'bodhi_update'}
                ],
                'verbose': False,
            }
        )

        waiverdb_api_post.assert_called_once_with(
            'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0/waivers/',
            {
                'username': 'guest',
                'comment': None,
                'waived': True,
                'product_version': 'fedora-17',
                'testcase': 'dist.rpmdeplint',
                'subject': {
                    'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'
                }
            }
        )

        assert list(res.json_body.keys()) == ['update']
        assert res.json_body['update'] == up.__json__()
        assert res.json_body['update']['test_gating_status'] == 'waiting'
        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        # The test gating status should not have been altered.
        assert up.test_gating_status == TestGatingStatus.waiting


class TestGetTestResults(BasePyTestCase):
    """
    This class contains tests for the get_test_results() function.
    """
    @mock.patch.dict(config, [('greenwave_api_url', None)])
    def test_cannot_get_test_results_when_no_greenwave_url(self, *args):
        """
        Ensure that we get an error if trying to get test results of an update
        when there is no greenwave_api_url defined in the configuration.
        """
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False

        res = self.app.get(f'/updates/{up.alias}/get-test-results', status=501)

        assert res.status_code == 501
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == "No greenwave_api_url specified"

    @mock.patch('bodhi.server.services.updates.Update.get_test_gating_info',
                side_effect=requests.Timeout('RequestsTimeout. oops!'))
    @mock.patch('bodhi.server.services.updates.log.error')
    def test_RequestsTimeout_exception(self, log_error, get_test_gating_info, *args):
        """Ensure that an RequestsTimeout Exception is handled by get_test_results()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False

        res = self.app.get(f'/updates/{up.alias}/get-test-results', status=504)

        assert res.status_code == 504
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'RequestsTimeout. oops!'
        log_error.assert_called_once()
        assert log_error.call_args_list[0][0][0] == (
            "Error querying greenwave for test results - timed out"
        )

    @mock.patch('bodhi.server.services.updates.Update.get_test_gating_info',
                side_effect=RuntimeError('RuntimeError. oops!'))
    @mock.patch('bodhi.server.services.updates.log.error')
    def test_RuntimeError_exception(self, log_error, get_test_gating_info, *args):
        """Ensure that an RuntimeError Exception is handled by get_test_results()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False

        res = self.app.get(f'/updates/{up.alias}/get-test-results', status=502)

        assert res.status_code == 502
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'RuntimeError. oops!'
        log_error.assert_called_once()
        assert log_error.call_args_list[0][0][0] == "Error querying greenwave for test results: %s"

    @mock.patch('bodhi.server.services.updates.Update.get_test_gating_info',
                side_effect=BodhiException('BodhiException. oops!'))
    @mock.patch('bodhi.server.services.updates.log.error')
    def test_BodhiException_exception(self, log_error, get_test_gating_info, *args):
        """Ensure that an BodhiException Exception is handled by get_test_results()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False

        res = self.app.get(f'/updates/{up.alias}/get-test-results', status=501)

        assert res.status_code == 501
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'BodhiException. oops!'
        log_error.assert_called_once()
        assert log_error.call_args_list[0][0][0] == "Failed to query greenwave for test results: %s"

    @mock.patch('bodhi.server.services.updates.Update.get_test_gating_info',
                side_effect=IOError('IOError. oops!'))
    @mock.patch('bodhi.server.services.updates.log.exception')
    def test_unexpected_exception(self, log_exception, get_test_gating_info, *args):
        """Ensure that an unexpected Exception is handled by get_test_results()."""
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False

        res = self.app.get(f'/updates/{up.alias}/get-test-results', status=500)

        assert res.status_code == 500
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'IOError. oops!'
        log_exception.assert_called_once_with("Unhandled exception in get_test_results")

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_erroring_on_greenwave(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument but that call raises an error.
        """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.locked = False
        call_api.side_effect = requests.exceptions.HTTPError(
            'Un-expected error foo bar')

        res = self.app.get(f'/updates/{update.alias}/get-test-results', status=502)

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': update.alias, 'type': 'bodhi_update'}
                ],
                'verbose': True,
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        assert res.json_body == {
            'errors': [
                {
                    'description': 'Un-expected error foo bar',
                    'location': 'body',
                    'name': 'request',
                }
            ],
            'status': 'error',
        }

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_timing_out_on_greenwave(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument but that call raises a TimeOut error.
        """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        call_api.side_effect = requests.exceptions.Timeout(
            'Request to greenwave timed out')

        res = self.app.get(f'/updates/{update.alias}/get-test-results', status=504)

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': update.alias, 'type': 'bodhi_update'}
                ],
                'verbose': True,
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        assert res.json_body == {
            'errors': [
                {
                    'description': 'Request to greenwave timed out',
                    'location': 'body',
                    'name': 'request',
                }
            ],
            'status': 'error',
        }

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_calling_greenwave(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument.
        """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        call_api.return_value = {"foo": "bar"}

        res = self.app.get(f'/updates/{update.alias}/get-test-results')

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': update.alias, 'type': 'bodhi_update'}
                ],
                'verbose': True,
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        assert res.json_body == {'decisions': [{'foo': 'bar'}]}

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_calling_greenwave_critpath(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        arguments for a critical path update.
        """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.critpath = True
        call_api.return_value = {"foo": "bar"}

        res = self.app.get(f'/updates/{update.alias}/get-test-results')

        assert call_api.call_args_list == [
            mock.call(
                'https://greenwave.api/decision',
                data={
                    'product_version': 'fedora-17',
                    'decision_context': context,
                    'subject': [
                        {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                        {'item': update.alias, 'type': 'bodhi_update'}
                    ],
                    'verbose': True,
                },
                method='POST',
                retries=3,
                service_name='Greenwave'
            ) for context in ('bodhi_update_push_testing_critpath', 'bodhi_update_push_testing')
        ]

        assert res.json_body == {'decisions': [{'foo': 'bar'}, {'foo': 'bar'}]}

    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_calling_greenwave_no_session(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument.
        """
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        call_api.return_value = {"foo": "bar"}

        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main(
                {}, testing='bodhi', session=self.db,
                greenwave_api_url='https://greenwave.api', **self.app_settings))
            res = app.get(f'/updates/{update.alias}/get-test-results')

        call_api.assert_called_once_with(
            'https://greenwave.api/decision',
            data={
                'product_version': 'fedora-17',
                'decision_context': 'bodhi_update_push_testing',
                'subject': [
                    {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                    {'item': update.alias, 'type': 'bodhi_update'}
                ],
                'verbose': True,
            },
            method='POST',
            retries=3,
            service_name='Greenwave'
        )

        assert res.json_body == {'decisions': [{'foo': 'bar'}]}

    @mock.patch('bodhi.server.util.call_api')
    def test_get_test_results_calling_greenwave_unauth(self, call_api, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument unauthenticated but the db does not know the specified update.
        """
        nvr = 'bodhi-2.0-1.fc17'
        call_api.return_value = {"foo": "bar"}

        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
            'greenwave_api_url': 'https://greenwave.api',
        })
        # with mock.patch('bodhi.server.Session.remove'):
        app = TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/updates/%s/get-test-results' % nvr, status=404)

        assert res.json_body == {
            'errors': [
                {
                    'description': 'Invalid update id',
                    'location': 'url',
                    'name': 'id',
                }
            ],
            'status': 'error',
        }

    @mock.patch.dict(config, [('greenwave_api_url', 'https://greenwave.api')])
    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.call_api', wraps=call_api)
    def test_get_test_results_calling_greenwave_500(self, call_api, http_session, *args):
        """
        Ensure if all conditions are met we do try to call greenwave with the proper
        argument but greenwave returns a 500 error
        """
        nvr = 'bodhi-2.0-1.fc17'
        request = mock.MagicMock()
        request.status_code = 500
        http_session.post.return_value = request

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.locked = False

        res = self.app.get(f'/updates/{up.alias}/get-test-results', status=502)

        assert call_api.call_count == 4
        assert res.json_body == {
            'errors': [
                {
                    'description': 'Bodhi failed to send POST request to '
                    'Greenwave at the following URL '
                    '"https://greenwave.api/decision". '
                    'The status code was "500".',
                    'location': 'body',
                    'name': 'request',
                }
            ],
            'status': 'error',
        }


class TestTriggerTests(BasePyTestCase):
    """
    This class contains tests for the trigger_tests() function.
    """
    def test_update_status_not_testing(self, *args):
        """
        Ensure that we get an error if trigger tests for update that is not
        in testing state.
        """
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.pending

        post_data = dict(
            csrf_token=self.get_csrf_token()
        )
        res = self.app.post_json(f'/updates/{up.alias}/trigger-tests', post_data, status=400)

        assert res.status_code == 400
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == "Update is not in testing status"

    def test_update_status_testing(self, *args):
        """
        Ensure that we publish message when update is in testing state.
        """
        nvr = 'bodhi-2.0-1.fc17'

        up = self.db.query(Build).filter_by(nvr=nvr).one().update
        up.status = UpdateStatus.testing

        with fml_testing.mock_sends(update_schemas.UpdateReadyForTestingV2):
            self.db.commit()

        post_data = dict(
            csrf_token=self.get_csrf_token()
        )
        with fml_testing.mock_sends(update_schemas.UpdateReadyForTestingV2):
            res = self.app.post_json(f'/updates/{up.alias}/trigger-tests', post_data, status=200)

        assert res.status_code == 200
