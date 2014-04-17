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

    def setUp(self):
        super(TestUsersService, self).setUp()

        session = DBSession()
        user = User(name=u'bodhi')
        session.add(user)
        session.flush()

    def test_404(self):
        self.app.get('/users/watwatwat', status=404)

    def test_list_users(self):
        res = self.app.get('/users/')
        body = res.json_body
        self.assertEquals(len(body['users']), 2)

        self.assertEquals(body['users'][0]['name'], u'guest')
        self.assertEquals(body['users'][1]['name'], u'bodhi')

    def test_list_users_with_pagination(self):
        res = self.app.get('/users/')
        body = res.json_body
        self.assertEquals(len(body['users']), 2)

        res = self.app.get('/users/', {'rows_per_page': 1})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

        res = self.app.get('/users/', {'rows_per_page': 1, 'page': 2})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'bodhi')

    def test_list_users_by_name(self):
        res = self.app.get('/users/', {"name": 'guest'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_name_match(self):
        res = self.app.get('/users/', {"name": 'gue%'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_name_match_miss(self):
        res = self.app.get('/users/', {"name": '%wat%'})
        self.assertEquals(len(res.json_body['users']), 0)

    def test_list_users_by_groups(self):
        res = self.app.get('/users/', {"groups": 'packager'})
        self.assertEquals(len(res.json_body['users']), 1)

    def test_list_users_by_nonexistant_group(self):
        res = self.app.get('/users/', {"groups": 'carbunkle'}, status=400)
        body = res.json_body
        self.assertEquals(body['errors'][0]['name'], 'groups')
        self.assertEquals(body['errors'][0]['description'],
                          'Invalid groups specified: carbunkle')

    def test_list_users_by_mixed_nonexistant_group(self):
        res = self.app.get('/users/', {"groups": ['carbunkle', 'packager']}, status=400)
        body = res.json_body
        self.assertEquals(body['errors'][0]['name'], 'groups')
        self.assertEquals(body['errors'][0]['description'],
                          'Invalid groups specified: carbunkle')

    def test_list_users_by_group_miss(self):
        res = self.app.get('/users/', {"groups": 'provenpackager'})
        body = res.json_body
        self.assertEquals(len(body['users']), 0)
        assert 'errors' not in res.json_body

    def test_list_users_by_update_title(self):
        res = self.app.get('/users/', {"updates": 'bodhi-2.0-1.fc17'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_update_alias(self):
        session = DBSession()
        update = session.query(Update).first()
        update.alias = 'some_alias'
        session.flush()

        res = self.app.get('/users/', {"updates": 'some_alias'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_nonexistant_update(self):
        res = self.app.get('/users/', {"updates": 'carbunkle'}, status=400)
        body = res.json_body
        self.assertEquals(res.json_body['errors'][0]['name'], 'updates')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid updates specified: carbunkle')

    def test_list_users_by_package_name(self):
        res = self.app.get('/users/', {"packages": 'bodhi'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_nonexistant_package(self):
        res = self.app.get('/users/', {"packages": 'carbunkle'}, status=400)
        body = res.json_body
        self.assertEquals(res.json_body['errors'][0]['name'], 'packages')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid packages specified: carbunkle')
