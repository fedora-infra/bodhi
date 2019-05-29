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
from unittest import mock
import os

import webtest

from bodhi import server
from bodhi.server.config import config
from bodhi.server.models import Build, Release, ReleaseState, Update, UpdateStatus
from bodhi.server.util import get_absolute_path
from bodhi.tests.server import base, create_update


class TestReleasesService(base.BaseTestCase):

    def setUp(self):
        super(TestReleasesService, self).setUp()

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
            branch='f22')

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
        self.assertEqual(r.state, ReleaseState.disabled)

    def test_get_single_release_by_lower(self):
        res = self.app.get('/releases/f22', headers={'Accept': 'application/json'})
        self.assertEqual(res.json_body['name'], 'F22')

    def test_get_single_release_by_upper(self):
        res = self.app.get('/releases/F22', headers={'Accept': 'application/json'})
        self.assertEqual(res.json_body['name'], 'F22')

    def test_get_single_release_by_long(self):
        res = self.app.get('/releases/Fedora%2022', headers={'Accept': 'application/json'})
        self.assertEqual(res.json_body['name'], 'F22')

    def test_list_releases(self):
        res = self.app.get('/releases/')
        body = res.json_body
        self.assertEqual(len(body['releases']), 2)

        self.assertEqual(body['releases'][0]['name'], 'F17')
        self.assertEqual(body['releases'][1]['name'], 'F22')

    def test_list_releases_with_pagination(self):
        res = self.app.get('/releases/')
        body = res.json_body
        self.assertEqual(len(body['releases']), 2)

        res = self.app.get('/releases/', {'rows_per_page': 1})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F17')

        res = self.app.get('/releases/', {'rows_per_page': 1, 'page': 2})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F22')

    def test_list_releases_by_ids_unknown(self):
        res = self.app.get('/releases/', {"ids": [9234872348923467]})

        self.assertEqual(len(res.json_body['releases']), 0)

    def test_list_releases_by_ids_plural(self):
        releases = Release.query.all()

        res = self.app.get('/releases/', {"ids": [release.id for release in releases]})

        self.assertEqual(len(res.json_body['releases']), len(releases))
        self.assertEqual(set([r['name'] for r in res.json_body['releases']]),
                         set([release.name for release in releases]))

    def test_list_releases_by_ids_singular(self):
        release = Release.query.all()[0]

        res = self.app.get('/releases/', {"ids": release.id})

        self.assertEqual(len(res.json_body['releases']), 1)
        self.assertEqual(res.json_body['releases'][0]['name'], release.name)

    def test_list_releases_by_name(self):
        res = self.app.get('/releases/', {"name": 'F22'})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F22')

    def test_list_releases_by_name_match(self):
        res = self.app.get('/releases/', {"name": '%1%'})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_name_match_miss(self):
        res = self.app.get('/releases/', {"name": '%wat%'})
        self.assertEqual(len(res.json_body['releases']), 0)

    def test_list_releases_by_update_alias(self):
        update = self.db.query(Update).first()
        update.alias = 'some_alias'
        self.db.flush()

        res = self.app.get('/releases/', {"updates": 'some_alias'})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_nonexistent_update(self):
        res = self.app.get('/releases/', {"updates": 'carbunkle'}, status=400)
        self.assertEqual(res.json_body['errors'][0]['name'], 'updates')
        self.assertEqual(res.json_body['errors'][0]['description'],
                         'Invalid updates specified: carbunkle')

    def test_list_releases_by_package_name(self):
        res = self.app.get('/releases/', {"packages": 'bodhi'})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_nonexistent_package(self):
        res = self.app.get('/releases/', {"packages": 'carbunkle'}, status=400)
        self.assertEqual(res.json_body['errors'][0]['name'], 'packages')
        self.assertEqual(res.json_body['errors'][0]['description'],
                         'Invalid packages specified: carbunkle')

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
                 "csrf_token": self.get_csrf_token(),
                 }
        self.app.post("/releases/", attrs, status=200)

        attrs.pop('csrf_token')

        r = self.db.query(Release).filter(Release.name == attrs["name"]).one()

        for k, v in attrs.items():
            self.assertEqual(getattr(r, k), v)

        self.assertEqual(r.state, ReleaseState.disabled)

    def test_list_releases_by_current_state(self):
        """ Test that we can filter releases using the 'current' state """
        res = self.app.get('/releases/', {"state": 'current'})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_disabled_state(self):
        """ Test that we can filter releases using the 'disabled' state """
        res = self.app.get('/releases/', {"state": 'disabled'})
        body = res.json_body
        self.assertEqual(len(body['releases']), 1)
        self.assertEqual(body['releases'][0]['name'], 'F22')

    def test_list_releases_by_pending_state(self):
        """ Test that we can filter releases using the 'pending' state """
        res = self.app.get('/releases/', {"state": 'pending'})
        body = res.json_body
        self.assertEqual(len(body['releases']), 0)

    def test_list_releases_with_a_wrong_state(self):
        """ Test that we get a 400 error when we use an undefined state """
        res = self.app.get('/releases/', {"state": 'active'}, status=400)
        body = res.json_body
        # the error description is not the same in Python2 and Python3
        # so let's just make sure we have an error.
        self.assertEqual(body['status'], 'error')

    def test_list_releases_exclude_archived_on(self):
        """ Test that we can filter releases using the exclude_archived flag"""
        r = Release.query.filter_by(name='F17').first()
        r.state = ReleaseState.archived
        r = Release.query.filter_by(name='F22').first()
        r.state = ReleaseState.current
        self.db.flush()

        res = self.app.get('/releases/', {"exclude_archived": True})

        body = res.json_body
        self.assertEqual([r['name'] for r in body['releases']], ['F22'])
        for r in body["releases"]:
            self.assertNotEqual(r["state"], ReleaseState.archived)

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
        self.assertEqual(len(body['releases']), 2)
        self.assertEqual({r['name'] for r in body['releases']}, {'F17', 'F22'})

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

        self.assertEqual(
            res.json,
            {"status": "error", "errors": [
                {"location": "body", "name": "release",
                 "description": "Unable to create/edit release: BOOM!"}]})
        # The release should not have been created.
        self.assertEqual(self.db.query(Release).filter(Release.name == attrs["name"]).count(), 0)
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

        self.assertEqual(len(res.json_body['errors']), 4)
        for error in res.json_body['errors']:
            self.assertEqual(error["description"], "Invalid tag: %s" % attrs[error["name"]])

    def test_edit_release(self):
        name = "F22"

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["state"] = "current"
        r["csrf_token"] = self.get_csrf_token()

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name == name).one()
        self.assertEqual(r.state, ReleaseState.current)

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
        self.assertEqual(r.mail_template, "fedora_modular_errata_template")

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
        self.assertEqual(r.mail_template, "fedora_errata_template")

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

        self.assertEqual(res.json_body['errors'][0]['name'], 'mail_template')
        self.assertEqual(res.json_body['errors'][0]['description'],
                         '"invalid_template_name" is not one of {}'.format(template_vals))

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

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name == name).one()
        self.assertEqual(r.state, ReleaseState.archived)

        # Expect update status not changed
        python_nose = self.db.query(Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        self.assertEqual(python_nose.status, UpdateStatus.stable)
        # Expect update status not changed
        python_paste_deploy = self.db.query(Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        self.assertEqual(python_paste_deploy.status, UpdateStatus.obsolete)
        # Expect update status not changed
        firefox = self.db.query(Build).filter_by(
            nvr='firefox-61.0.2-3.fc17').one().update
        self.assertEqual(firefox.status, UpdateStatus.unpushed)
        # Expect update status changed to 'obsolete'
        bodhi_update = self.db.query(Build).filter_by(
            nvr='bodhi-2.0-1.fc17').one().update
        self.assertEqual(bodhi_update.status, UpdateStatus.obsolete)
        # Check for the comment
        expected_comment = ('This update is marked obsolete because the F17 release '
                            'is archived.')
        self.assertEqual(bodhi_update.comments[-1].text, expected_comment)
        # Expect update status not changed
        python_test_update = self.db.query(Build).filter_by(
            nvr='python-test-update.fc22').one().update
        self.assertEqual(python_test_update.status, UpdateStatus.pending)

    def test_get_single_release_html(self):
        res = self.app.get('/releases/f17', headers={'Accept': 'text/html'})
        self.assertEqual(res.content_type, 'text/html')
        self.assertIn('f17-updates-testing', res)

    def test_get_single_release_html_two_same_updates_same_month(self):
        """Test the HTML view with two updates of the same type from the same month."""
        create_update(self.db, ['bodhi-3.4.0-1.fc27'])
        create_update(self.db, ['rust-chan-0.3.1-1.fc27'])
        self.db.flush()

        res = self.app.get('/releases/f17', headers={'Accept': 'text/html'})

        self.assertEqual(res.content_type, 'text/html')
        self.assertIn('f17-updates-testing', res)
        # Since the updates are the same type and from the same month, we should see a count of 2 in
        # the graph data.
        graph_data = 'data : [\n                2,\n              ]'
        self.assertTrue(graph_data in res)

    def test_get_non_existent_release_html(self):
        self.app.get('/releases/x', headers={'Accept': 'text/html'}, status=404)

    def test_get_releases_html(self):
        res = self.app.get('/releases/', headers={'Accept': 'text/html'})
        self.assertEqual(res.content_type, 'text/html')
        self.assertIn('Fedora 22', res)

    def test_query_releases_html_two_releases_same_state(self):
        """Test query_releases_html() with two releases in the same state."""
        attrs = {
            "name": "F42", "long_name": "Fedora 42", "version": "42",
            "id_prefix": "FEDORA", "branch": "f42", "dist_tag": "f42",
            "stable_tag": "f42-updates",
            "testing_tag": "f42-updates-testing",
            "candidate_tag": "f42-updates-candidate",
            "pending_stable_tag": "f42-updates-pending",
            "pending_signing_tag": "f42-updates-testing-signing",
            "pending_testing_tag": "f42-updates-testing-pending",
            "override_tag": "f42-override",
            "csrf_token": self.get_csrf_token()}
        self.app.post("/releases/", attrs, status=200)

        res = self.app.get('/releases/', headers={'Accept': 'text/html'})

        self.assertEqual(res.content_type, 'text/html')
        self.assertIn('Fedora 22', res)
        self.assertIn('Fedora 42', res)
