# Copyright © 2014-2019 Red Hat, Inc. and others.
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
from datetime import date, datetime
from unittest import mock
import os

from fedora_messaging import testing as fml_testing
import webtest

from bodhi import server
from bodhi.server.config import config
from bodhi.server.models import (
    Build,
    PackageManager,
    Release,
    ReleaseState,
    Update,
    UpdateRequest,
    UpdateStatus,
    UpdateType,
    User,
)
from bodhi.server.util import get_absolute_path
from bodhi.server.views import generic

from .. import base


class TestReleasesService(base.BasePyTestCase):

    def setup_method(self, method):
        super().setup_method(method)

        release = Release(
            name='F22', long_name='Fedora 22',
            id_prefix='FEDORA', version='22',
            dist_tag='f22', stable_tag='f22-updates',
            testing_tag='f22-updates-testing',
            candidate_tag='f22-updates-candidate',
            pending_signing_tag='f22-updates-testing-signing',
            pending_testing_tag='f22-updates-testing-pending',
            pending_stable_tag='f22-updates-pending',
            override_tag='f22-override',
            branch='f22',
            package_manager=PackageManager.dnf,
            testing_repository='updates-testing',
            eol=date(2016, 6, 14))

        self.db.add(release)
        self.db.commit()

    def test_404(self):
        self.app.get('/releases/watwatwat', status=404)

    def test_anonymous_cant_edit_release(self):
        """Ensure that an unauthenticated user cannot edit a release, since only an admin should."""
        name = "F22"
        # Create a new app so we are the anonymous user.
        with mock.patch('bodhi.server.Session.remove'):
            app = webtest.TestApp(server.main({}, session=self.db, **self.app_settings))

        res = app.get('/releases/%s' % name, status=200)
        r = res.json_body
        r["edited"] = name
        r["state"] = "current"
        r["csrf_token"] = self.get_csrf_token()

        # The anonymous user should receive a 403.
        res = app.post("/releases/", r, status=403)

        r = self.db.query(Release).filter(Release.name == name).one()
        assert r.state == ReleaseState.disabled

    def test_get_single_release_by_lower(self):
        res = self.app.get('/releases/f22', headers={'Accept': 'application/json'})
        assert res.json_body['name'] == 'F22'

    def test_get_single_release_by_upper(self):
        res = self.app.get('/releases/F22', headers={'Accept': 'application/json'})
        assert res.json_body['name'] == 'F22'

    def test_get_single_release_by_long(self):
        res = self.app.get('/releases/Fedora%2022', headers={'Accept': 'application/json'})
        assert res.json_body['name'] == 'F22'

    def test_get_release_eol(self):
        res = self.app.get('/releases/Fedora%2022', headers={'Accept': 'application/json'})
        assert res.json_body['eol'] == '2016-06-14'

    def test_list_releases(self):
        res = self.app.get('/releases/')
        body = res.json_body
        assert len(body['releases']) == 2

        assert body['releases'][0]['name'] == 'F17'
        assert body['releases'][1]['name'] == 'F22'

    def test_list_releases_with_pagination(self):
        res = self.app.get('/releases/')
        body = res.json_body
        assert len(body['releases']) == 2

        res = self.app.get('/releases/', {'rows_per_page': 1})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F17'

        res = self.app.get('/releases/', {'rows_per_page': 1, 'page': 2})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F22'

    def test_list_releases_by_ids_unknown(self):
        res = self.app.get('/releases/', {"ids": [9234872348923467]})

        assert len(res.json_body['releases']) == 0

    def test_list_releases_by_ids_plural(self):
        releases = Release.query.all()

        res = self.app.get('/releases/', {"ids": [release.id for release in releases]})

        assert len(res.json_body['releases']) == len(releases)
        assert set([r['name'] for r in res.json_body['releases']]) == \
            set([release.name for release in releases])

    def test_list_releases_by_ids_singular(self):
        release = Release.query.all()[0]

        res = self.app.get('/releases/', {"ids": release.id})

        assert len(res.json_body['releases']) == 1
        assert res.json_body['releases'][0]['name'] == release.name

    def test_list_releases_by_name(self):
        res = self.app.get('/releases/', {"name": 'F22'})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F22'

    def test_list_releases_by_name_match(self):
        res = self.app.get('/releases/', {"name": '%1%'})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F17'

    def test_list_releases_by_name_match_miss(self):
        res = self.app.get('/releases/', {"name": '%wat%'})
        assert len(res.json_body['releases']) == 0

    def test_list_releases_by_update_alias(self):
        update = self.db.query(Update).first()
        update.alias = 'some_alias'
        self.db.flush()

        res = self.app.get('/releases/', {"updates": 'some_alias'})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F17'

    def test_list_releases_by_nonexistent_update(self):
        res = self.app.get('/releases/', {"updates": 'carbunkle'}, status=400)
        assert res.json_body['errors'][0]['name'] == 'updates'
        assert res.json_body['errors'][0]['description'] == \
            'Invalid updates specified: carbunkle'

    def test_list_releases_by_package_name(self):
        res = self.app.get('/releases/', {"packages": 'bodhi'})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F17'

    def test_list_releases_by_nonexistent_package(self):
        res = self.app.get('/releases/', {"packages": 'carbunkle'}, status=400)
        assert res.json_body['errors'][0]['name'] == 'packages'
        assert res.json_body['errors'][0]['description'] == \
            'Invalid packages specified: carbunkle'

    def test_new_release(self):
        attrs = {"name": "F42", "long_name": "Fedora 42", "version": "42",
                 "id_prefix": "FEDORA", "branch": "f42", "dist_tag": "f42",
                 "stable_tag": "f42-updates",
                 "testing_tag": "f42-updates-testing",
                 "candidate_tag": "f42-updates-candidate",
                 "pending_stable_tag": "f42-updates-pending",
                 "pending_signing_tag": "f42-updates-testing-signing",
                 "pending_testing_tag": "f42-updates-testing-pending",
                 "override_tag": "f42-override",
                 "package_manager": "dnf",
                 "testing_repository": "updates-testing",
                 "eol": date(2016, 6, 14),
                 "csrf_token": self.get_csrf_token(),
                 }
        self.app.post("/releases/", attrs, status=200)

        attrs.pop('csrf_token')
        attrs.pop('eol')

        r = self.db.query(Release).filter(Release.name == attrs["name"]).one()

        for k, v in attrs.items():
            if k in ['state', 'package_manager']:
                assert getattr(r, k).value == v
            else:
                assert getattr(r, k) == v

        assert r.state == ReleaseState.disabled

        # Let's check Release cache content
        releases = Release.all_releases()
        disabled_releases = releases["disabled"]
        assert disabled_releases[0]["name"] == "F42"
        assert disabled_releases[1]["name"] == "F22"
        assert len(disabled_releases) == 2
        current_releases = releases["current"]
        assert current_releases[0]["name"] == "F17"
        assert len(current_releases) == 1

    def test_list_releases_by_current_state(self):
        """ Test that we can filter releases using the 'current' state """
        res = self.app.get('/releases/', {"state": 'current'})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F17'

    def test_list_releases_by_disabled_state(self):
        """ Test that we can filter releases using the 'disabled' state """
        res = self.app.get('/releases/', {"state": 'disabled'})
        body = res.json_body
        assert len(body['releases']) == 1
        assert body['releases'][0]['name'] == 'F22'

    def test_list_releases_by_pending_state(self):
        """ Test that we can filter releases using the 'pending' state """
        res = self.app.get('/releases/', {"state": 'pending'})
        body = res.json_body
        assert len(body['releases']) == 0

    def test_list_releases_with_a_wrong_state(self):
        """ Test that we get a 400 error when we use an undefined state """
        res = self.app.get('/releases/', {"state": 'active'}, status=400)
        body = res.json_body
        # the error description is not the same in Python2 and Python3
        # so let's just make sure we have an error.
        assert body['status'] == 'error'

    def test_list_releases_exclude_archived_on(self):
        """ Test that we can filter releases using the exclude_archived flag"""
        r = Release.query.filter_by(name='F17').first()
        r.state = ReleaseState.archived
        r = Release.query.filter_by(name='F22').first()
        r.state = ReleaseState.current
        self.db.flush()

        res = self.app.get('/releases/', {"exclude_archived": True})

        body = res.json_body
        assert [r['name'] for r in body['releases']] == ['F22']
        for r in body["releases"]:
            assert r["state"] != ReleaseState.archived

    def test_list_releases_exclude_archived_off(self):
        """
        Test that "archived" releases are included in response when the exclude_archived is off
        """
        r = Release.query.filter_by(name='F17').first()
        r.state = ReleaseState.archived
        r = Release.query.filter_by(name='F22').first()
        r.state = ReleaseState.current
        self.db.flush()

        res = self.app.get('/releases/')

        body = res.json_body
        assert len(body['releases']) == 2
        assert {r['name'] for r in body['releases']} == {'F17', 'F22'}

    @mock.patch('bodhi.server.services.releases.log.info', side_effect=IOError('BOOM!'))
    def test_save_release_exception_handler(self, info):
        """Test the exception handler in save_release()."""
        attrs = {"name": "F42", "long_name": "Fedora 42", "version": "42",
                 "id_prefix": "FEDORA", "branch": "f42", "dist_tag": "f42",
                 "stable_tag": "f42-updates",
                 "testing_tag": "f42-updates-testing",
                 "candidate_tag": "f42-updates-candidate",
                 "pending_stable_tag": "f42-updates-pending",
                 "pending_signing_tag": "f42-updates-testing-signing",
                 "pending_testing_tag": "f42-updates-testing-pending",
                 "override_tag": "f42-override",
                 "csrf_token": self.get_csrf_token(),
                 }

        res = self.app.post("/releases/", attrs, status=400)

        assert res.json == {"status": "error", "errors": [
            {"location": "body", "name": "release",
             "description": "Unable to create/edit release: BOOM!"}]}
        # The release should not have been created.
        assert self.db.query(Release).filter(Release.name == attrs["name"]).count() == 0
        info.assert_called_once_with('Creating a new release: F42')

    @mock.patch('bodhi.server.services.releases.log.info', side_effect=IOError('BOOM!'))
    def test_save_release_exception_handler_with_eol(self, info):
        """Test the exception handler in save_release()."""
        attrs = {"name": "F42", "long_name": "Fedora 42", "version": "42",
                 "id_prefix": "FEDORA", "branch": "f42", "dist_tag": "f42",
                 "stable_tag": "f42-updates",
                 "testing_tag": "f42-updates-testing",
                 "candidate_tag": "f42-updates-candidate",
                 "pending_stable_tag": "f42-updates-pending",
                 "pending_signing_tag": "f42-updates-testing-signing",
                 "pending_testing_tag": "f42-updates-testing-pending",
                 "override_tag": "f42-override",
                 "csrf_token": self.get_csrf_token(), "eol": date(2016, 6, 16),
                 }

        res = self.app.post("/releases/", attrs, status=400)

        assert res.json == {"status": "error", "errors": [
            {"location": "body", "name": "release",
             "description": "Unable to create/edit release: BOOM!"}]}
        # The release should not have been created.
        assert self.db.query(Release).filter(Release.name == attrs["name"]).count() == 0
        info.assert_called_once_with('Creating a new release: F42')

    def test_new_release_invalid_tags(self):
        attrs = {"name": "EL42", "long_name": "EPEL 42", "version": "42",
                 "id_prefix": "FEDORA EPEL", "branch": "f42",
                 "dist_tag": "epel42", "stable_tag": "epel42",
                 "testing_tag": "epel42-testing",
                 "candidate_tag": "epel42-candidate",
                 "override_tag": "epel42-override",
                 "csrf_token": self.get_csrf_token(),
                 }
        res = self.app.post("/releases/", attrs, status=400)

        assert len(res.json_body['errors']) == 4
        for error in res.json_body['errors']:
            assert error["description"] == "Invalid tag: %s" % attrs[error["name"]]

    def test_edit_release(self):
        name = "F22"

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["state"] = "current"
        r["csrf_token"] = self.get_csrf_token()

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name == name).one()
        assert r.state == ReleaseState.current

    def test_edit_mail_template(self):
        """Test `mail_template` is saved correctly in db after release edit."""
        name = "F22"

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["mail_template"] = "fedora_modular_errata_template"
        r["csrf_token"] = self.get_csrf_token()

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name == name).one()
        assert r.mail_template == "fedora_modular_errata_template"

    def test_edit_mail_template_with_null_value(self):
        """Test that null value for `mail_template` gets replaced by default value."""
        name = "F22"

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["mail_template"] = ""
        r["csrf_token"] = self.get_csrf_token()

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name == name).one()
        assert r.mail_template == "fedora_errata_template"

    def test_edit_mail_template_with_invalid_value(self):
        """Test appropriate error is returned when provided `mail_template` doesn't exist."""
        name = "F22"
        location = config.get('mail.templates_basepath')
        directory = get_absolute_path(location)
        template_list = [os.path.splitext(file)[0] for file in os.listdir(directory)]
        template_vals = ", ".join(template_list)

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["mail_template"] = "invalid_template_name"
        r["csrf_token"] = self.get_csrf_token()

        res = self.app.post("/releases/", r, status=400)

        assert res.json_body['errors'][0]['name'] == 'mail_template'
        assert res.json_body['errors'][0]['description'] == \
            f'"invalid_template_name" is not one of {template_vals}'

    def test_change_release_state_to_archived(self):
        """
        Test that when we make release archived, all release updates state will change to
        'obsolete' or stay 'stable'/'unpushed'
        """
        python_nose = self.create_update(['python-nose-1.3.7-11.fc17'])
        python_paste_deploy = self.create_update(['python-paste-deploy-1.5.2-8.fc17'])
        firefox = self.create_update(['firefox-61.0.2-3.fc17'])
        python_test_update = self.create_update(['python-test-update.fc22'], 'F22')
        # Change status of F17 updates
        python_nose.status = UpdateStatus.stable
        python_paste_deploy.status = UpdateStatus.obsolete
        firefox.status = UpdateStatus.unpushed
        self.db.commit()
        name = "F17"

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["state"] = "archived"
        r["csrf_token"] = self.get_csrf_token()
        r.pop("eol")

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name == name).one()
        assert r.state == ReleaseState.archived

        # Expect update status not changed
        python_nose = self.db.query(Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        assert python_nose.status == UpdateStatus.stable
        # Expect update status not changed
        python_paste_deploy = self.db.query(Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        assert python_paste_deploy.status == UpdateStatus.obsolete
        # Expect update status not changed
        firefox = self.db.query(Build).filter_by(
            nvr='firefox-61.0.2-3.fc17').one().update
        assert firefox.status == UpdateStatus.unpushed
        # Expect update status changed to 'obsolete'
        bodhi_update = self.db.query(Build).filter_by(
            nvr='bodhi-2.0-1.fc17').one().update
        assert bodhi_update.status == UpdateStatus.obsolete
        assert bodhi_update.request == None
        # Check for the comment
        expected_comment = ('This update is marked obsolete because the F17 release '
                            'is archived.')
        assert bodhi_update.comments[-1].text == expected_comment
        # Expect update status not changed
        python_test_update = self.db.query(Build).filter_by(
            nvr='python-test-update.fc22').one().update
        assert python_test_update.status == UpdateStatus.pending

    def test_change_release_state_to_frozen(self):
        """
        Test that when we make release frozen, Bodhi will create comment about delayed
        push to stable in all updates requested to stable
        """
        python_test_update = self.create_update(['python-test-update.fc22'], 'F22')
        # Change request to stable in python_test_update
        python_test_update.status = UpdateStatus.testing
        python_test_update.request = UpdateRequest.stable
        self.db.commit()
        name = "F22"

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["state"] = "frozen"
        r["csrf_token"] = self.get_csrf_token()

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name == name).one()
        assert r.state == ReleaseState.frozen

        # Check for the comment
        python_test_update = self.db.query(Build).filter_by(
            nvr='python-test-update.fc22').one().update
        expected_comment = ('There is an ongoing freeze; this will be pushed to'
                            ' stable after the freeze is over.')
        assert python_test_update.comments[-1].text == expected_comment

    def test_get_single_release_html(self):
        res = self.app.get('/releases/f17', headers={'Accept': 'text/html'})
        assert res.content_type == 'text/html'
        assert 'f17-updates-testing' in res

    def test_get_single_release_html_two_same_updates_same_month(self):
        """Test the HTML view with two updates of the same type from the same month."""
        base.create_update(self.db, ['bodhi-3.4.0-1.fc27'])
        base.create_update(self.db, ['rust-chan-0.3.1-1.fc27'])
        self.db.flush()

        res = self.app.get('/releases/f17', headers={'Accept': 'text/html'})

        assert res.content_type == 'text/html'
        assert 'f17-updates-testing' in res
        # Since the updates are the same type and from the same month, we should see a count of 2 in
        # the graph data.
        graph_data = 'data : [\n            2,\n          ]'
        assert graph_data in res

    def test_get_non_existent_release_html(self):
        self.app.get('/releases/x', headers={'Accept': 'text/html'}, status=404)


class TestReleasesHTML(base.BasePyTestCase):
    def setup_method(self, method):
        super().setup_method(method)

        def _add_updates(updateslist, user, release, packagesuffix):
            """Private method that adds updates to the database for testing

            """
            count = 0
            for i in updateslist:
                for j in i[1]:
                    for k in range(0, j[1]):
                        update = Update(
                            user=user,
                            status=i[0],
                            type=j[0],
                            notes='Useful details!',
                            release=release,
                            date_submitted=datetime(1984, 11, 2),
                            requirements='rpmlint',
                            stable_karma=3,
                            unstable_karma=-3,
                        )
                        self.db.add(update)
                        self.db.commit()
                        count = count + 1

        user2 = User(name='dudemcpants')
        self.db.flush()
        self.db.add(user2)

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
            branch='f18', state=ReleaseState.pending)
        self.db.add(release)

        currentrelease = self.db.query(Release).filter_by(name='F17').one()
        addedupdates = [[UpdateStatus.pending,
                         [[UpdateType.security, 5],
                          [UpdateType.bugfix, 4],
                          [UpdateType.enhancement, 3],
                          [UpdateType.newpackage, 2]]],
                        [UpdateStatus.testing,
                         [[UpdateType.security, 15],
                          [UpdateType.bugfix, 14],
                          [UpdateType.enhancement, 13],
                          [UpdateType.newpackage, 12]]],
                        [UpdateStatus.stable,
                         [[UpdateType.security, 25],
                          [UpdateType.bugfix, 24],
                          [UpdateType.enhancement, 23],
                          [UpdateType.newpackage, 22]]]]

        with fml_testing.mock_sends():
            _add_updates(addedupdates, user2, currentrelease, "fc17")

        pendingrelease = self.db.query(Release).filter_by(name='F18').one()
        addedupdates2 = [[UpdateStatus.pending,
                         [[UpdateType.security, 2],
                          [UpdateType.bugfix, 2],
                          [UpdateType.enhancement, 2],
                          [UpdateType.newpackage, 2]]],
                         [UpdateStatus.testing,
                          [[UpdateType.security, 3],
                           [UpdateType.bugfix, 3],
                           [UpdateType.enhancement, 3],
                           [UpdateType.newpackage, 3]]],
                         [UpdateStatus.stable,
                          [[UpdateType.security, 4],
                           [UpdateType.bugfix, 4],
                           [UpdateType.enhancement, 4],
                           [UpdateType.newpackage, 4]]]]
        with fml_testing.mock_sends():
            _add_updates(addedupdates2, user2, pendingrelease, "fc18")
        self.db.flush()
        # Clear the caches
        Release._tag_cache = None
        generic._generate_home_page_stats.invalidate()

    def test_release_counts(self):
        """Test the release page update counts"""
        res = self.app.get('/releases/', headers={'Accept': 'text/html'}, status=200)
        # Assert that pending updates counts in a current release are displayed properly
        # Note the bug update count here is one more than what we generate above
        # because there is already a single update in the test data.
        assert '?releases=F17&amp;status=pending">15' in res

        # Assert that testing updates counts in a current release are displayed properly
        assert '?releases=F17&amp;status=testing">54' in res

        # Assert that testing updates counts in a pending release are displayed properly
        assert '?releases=F18&amp;status=testing">12' in res

        # Assert that stable updates counts in a pending release are displayed properly
        assert '?releases=F18&amp;status=stable">16' in res
