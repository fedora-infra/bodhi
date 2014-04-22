from datetime import datetime, timedelta
from webtest import TestApp

import bodhi.tests.functional.base

from bodhi import main
from bodhi.models import (
    Base,
    Bug,
    Build,
    CVE,
    DBSession,
    Group,
    Package,
    Release,
    Update,
    UpdateType,
    UpdateStatus,
    UpdateRequest,
)


class TestReleasesService(bodhi.tests.functional.base.BaseWSGICase):

    def setUp(self):
        super(TestReleasesService, self).setUp()

        session = DBSession()
        release = Release(
            name=u'F22', long_name=u'Fedora 22',
            id_prefix=u'FEDORA', dist_tag=u'f22', version='22')
        session.add(release)
        session.flush()

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
        session = DBSession()
        update = session.query(Update).first()
        update.alias = 'some_alias'
        session.flush()

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
