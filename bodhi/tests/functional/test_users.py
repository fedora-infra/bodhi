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
    User,
    UpdateStatus,
    UpdateRequest,
)


class TestUsersService(bodhi.tests.functional.base.BaseWSGICase):

    def test_404(self):
        self.app.get('/users/watwatwat', status=404)

    def test_list_users(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/')
        body = res.json_body
        self.assertEquals(len(body['users']), 1)

        user = body['users'][0]
        self.assertEquals(user['name'], u'guest')

    def test_list_users_pagination(self):
        raise self.skipTest('Not yet implemented')
        raise NotImplementedError(
            """ Need to write the fixture to insert a second user in order to
            test pagination..
            """
        )

    def test_list_users_by_name(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"name": 'guest'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_name_match(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"name": 'gue*'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_name_match_miss(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"name": '*wat*'})
        body = res.json_body
        self.assertEquals(len(body['users']), 0)

    def test_list_users_by_groups(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"groups": 'packager'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)

    def test_list_users_by_nonexistant_group(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"groups": 'carbunkle'})
        body = res.json_body
        self.assertEquals(len(body['users']), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'groups.0')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"carbunkle" is not a group')

    def test_list_users_by_group_miss(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"groups": 'provenpackager'})
        body = res.json_body
        self.assertEquals(len(body['users']), 0)
        assert 'errors' not in res.json_body

    def test_list_users_by_update_title(self):
        raise self.skipTest('Not yet implemented')
        raise NotImplementedError(
            """ How do we handle querying for
            update submitters versus update commenters
            do we always return both given an update title?
            do we use a flag to say "give me only the owner"
            or "give me only the commenters" or "give me both"?
            """
        )
        res = self.app.get('/users/',
                           {"updates": 'bodhi-2.0-1.fc17'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_update_alias(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"updates": 'some_alias_here'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_nonexistant_update(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"updates": 'carbunkle'})
        body = res.json_body
        self.assertEquals(len(body['users']), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'updates.0')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"carbunkle" is not an update')

    def test_list_users_by_package_title(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"packages": 'bodhi'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_nonexistant_package(self):
        raise self.skipTest('Not yet implemented')
        res = self.app.get('/users/',
                           {"packages": 'carbunkle'})
        body = res.json_body
        self.assertEquals(len(body['users']), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'packages.0')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"carbunkle" is not a package')
