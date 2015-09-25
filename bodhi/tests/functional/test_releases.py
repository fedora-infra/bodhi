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

import bodhi.tests.functional.base

from bodhi.models import (
    Release,
    ReleaseState,
    Update,
)


class TestReleasesService(bodhi.tests.functional.base.BaseWSGICase):

    def setUp(self):
        super(TestReleasesService, self).setUp()

        release = Release(
            name=u'F22', long_name=u'Fedora 22',
            id_prefix=u'FEDORA', version=u'22',
            dist_tag=u'f22', stable_tag=u'f22-updates',
            testing_tag=u'f22-updates-testing',
            candidate_tag=u'f22-updates-candidate',
            pending_testing_tag=u'f22-updates-testing-pending',
            pending_stable_tag=u'f22-updates-pending',
            override_tag=u'f22-override',
            branch=u'f22')

        self.db.add(release)
        self.db.flush()

    def test_404(self):
        self.app.get('/releases/watwatwat', status=404)

    def test_get_single_release_by_lower(self):
        res = self.app.get('/releases/f22')
        self.assertEquals(res.json_body['name'], 'F22')

    def test_get_single_release_by_upper(self):
        res = self.app.get('/releases/F22')
        self.assertEquals(res.json_body['name'], 'F22')

    def test_get_single_release_by_long(self):
        res = self.app.get('/releases/Fedora%2022')
        self.assertEquals(res.json_body['name'], 'F22')

    def test_list_releases(self):
        res = self.app.get('/releases/')
        body = res.json_body
        self.assertEquals(len(body['releases']), 2)

        self.assertEquals(body['releases'][0]['name'], u'F17')
        self.assertEquals(body['releases'][1]['name'], u'F22')

    def test_list_releases_with_pagination(self):
        res = self.app.get('/releases/')
        body = res.json_body
        self.assertEquals(len(body['releases']), 2)

        res = self.app.get('/releases/', {'rows_per_page': 1})
        body = res.json_body
        self.assertEquals(len(body['releases']), 1)
        self.assertEquals(body['releases'][0]['name'], 'F17')

        res = self.app.get('/releases/', {'rows_per_page': 1, 'page': 2})
        body = res.json_body
        self.assertEquals(len(body['releases']), 1)
        self.assertEquals(body['releases'][0]['name'], 'F22')

    def test_list_releases_by_name(self):
        res = self.app.get('/releases/', {"name": 'F22'})
        body = res.json_body
        self.assertEquals(len(body['releases']), 1)
        self.assertEquals(body['releases'][0]['name'], 'F22')

    def test_list_releases_by_name_match(self):
        res = self.app.get('/releases/', {"name": '%1%'})
        body = res.json_body
        self.assertEquals(len(body['releases']), 1)
        self.assertEquals(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_name_match_miss(self):
        res = self.app.get('/releases/', {"name": '%wat%'})
        self.assertEquals(len(res.json_body['releases']), 0)

    def test_list_releases_by_update_title(self):
        res = self.app.get('/releases/', {"updates": 'bodhi-2.0-1.fc17'})
        body = res.json_body
        self.assertEquals(len(body['releases']), 1)
        self.assertEquals(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_update_alias(self):
        update = self.db.query(Update).first()
        update.alias = u'some_alias'
        self.db.flush()

        res = self.app.get('/releases/', {"updates": 'some_alias'})
        body = res.json_body
        self.assertEquals(len(body['releases']), 1)
        self.assertEquals(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_nonexistant_update(self):
        res = self.app.get('/releases/', {"updates": 'carbunkle'}, status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'updates')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid updates specified: carbunkle')

    def test_list_releases_by_package_name(self):
        res = self.app.get('/releases/', {"packages": 'bodhi'})
        body = res.json_body
        self.assertEquals(len(body['releases']), 1)
        self.assertEquals(body['releases'][0]['name'], 'F17')

    def test_list_releases_by_nonexistant_package(self):
        res = self.app.get('/releases/', {"packages": 'carbunkle'}, status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'packages')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid packages specified: carbunkle')

    def test_new_release(self):
        attrs = {"name": "F42", "long_name": "Fedora 42", "version": "42",
                 "id_prefix": "FEDORA", "branch": "f42", "dist_tag": "f42",
                 "stable_tag": "f42-updates",
                 "testing_tag": "f42-updates-testing",
                 "candidate_tag": "f42-updates-candidate",
                 "pending_stable_tag": "f42-updates-pending",
                 "pending_testing_tag": "f42-updates-testing-pending",
                 "override_tag": "f42-override",
                 "csrf_token": self.get_csrf_token(),
                 }
        self.app.post("/releases/", attrs, status=200)

        attrs.pop('csrf_token')

        r = self.db.query(Release).filter(Release.name==attrs["name"]).one()

        for k, v in attrs.items():
            self.assertEquals(getattr(r, k), v)

        self.assertEquals(r.state, ReleaseState.disabled)

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

        self.assertEquals(len(res.json_body['errors']), 4)
        for error in res.json_body['errors']:
            self.assertEquals(error["description"], "Invalid tag: %s" % attrs[error["name"]])

    def test_edit_release(self):
        name = u"F22"

        res = self.app.get('/releases/%s' % name, status=200)
        r = res.json_body

        r["edited"] = name
        r["state"] = "current"
        r["csrf_token"] = self.get_csrf_token()

        res = self.app.post("/releases/", r, status=200)

        r = self.db.query(Release).filter(Release.name==name).one()
        self.assertEquals(r.state, ReleaseState.current)

    def test_get_single_release_html(self):
        res = self.app.get('/releases/f17', headers={'Accept': 'text/html'})
        self.assertEquals(res.content_type, 'text/html')
        self.assertIn('f17-updates-testing', res)

    def test_get_non_existent_release_html(self):
        self.app.get('/releases/x', headers={'Accept': 'text/html'}, status=404)

    def test_get_releases_html(self):
        res = self.app.get('/releases/', headers={'Accept': 'text/html'})
        self.assertEquals(res.content_type, 'text/html')
        self.assertIn('Fedora 22', res)
