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

from pyramid.settings import asbool

import bodhi.tests.functional.base

from bodhi.config import config
from bodhi.models import (
    Update,
    User,
)


class TestUsersService(bodhi.tests.functional.base.BaseWSGICase):

    def setUp(self):
        super(TestUsersService, self).setUp()

        user = User(name=u'bodhi')
        self.db.add(user)
        self.db.flush()

    def test_404(self):
        self.app.get('/users/watwatwat', status=404)

    def test_get_single_user(self):
        res = self.app.get('/users/bodhi')
        self.assertEquals(res.json_body['user']['name'], 'bodhi')

    def test_get_hardcoded_avatar(self):
        res = self.app.get('/users/bodhi')
        self.assertEquals(res.json_body['user']['name'], 'bodhi')
        url = 'https://apps.fedoraproject.org/img/icons/bodhi-24.png'
        self.assertEquals(res.json_body['user']['avatar'], url)

    def test_get_single_avatar(self):
        res = self.app.get('/users/guest')
        self.assertEquals(res.json_body['user']['name'], 'guest')

        if not asbool(config.get('libravatar_enabled', True)):
            return

        base = 'https://seccdn.libravatar.org/avatar/'
        h = 'eb48e08cc23bcd5961de9541ba5156c385cd39799e1dbf511477aa4d4d3a37e7'
        tail = '?d=retro&s=24'
        url = base + h

        self.assertEquals(res.json_body['user']['avatar'][:-len(tail)], url)

    def test_get_single_user_page(self):
        res = self.app.get('/users/guest', headers=dict(accept='text/html'))
        self.assertIn('text/html', res.headers['Content-Type'])
        self.assertIn('libravatar.org', res)
        self.assertIn('&copy;', res)

    def test_get_single_user_jsonp(self):
        res = self.app.get('/users/guest',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        self.assertIn('application/javascript', res.headers['Content-Type'])
        self.assertIn('libravatar.org', res)

    def test_get_single_user_rss(self):
        self.app.get('/users/bodhi',
                     headers=dict(accept='application/atom+xml'),
                     status=406)

    def test_list_users(self):
        res = self.app.get('/users/')
        self.assertIn('application/json', res.headers['Content-Type'])
        body = res.json_body
        self.assertEquals(len(body['users']), 3)

        users = [user['name'] for user in body['users']]
        self.assertIn(u'guest', users)
        self.assertIn(u'anonymous', users)
        self.assertIn(u'bodhi', users)

    def test_list_users_jsonp(self):
        res = self.app.get('/users/',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        self.assertIn('application/javascript', res.headers['Content-Type'])
        self.assertIn('callback', res)
        self.assertIn('bodhi', res)
        self.assertIn('guest', res)
        # FIXME: for some reason this bounces between 3 and 4
        # check to catch performance regressions
        #self.assertEquals(len(self.sql_statements), 4)

    def test_list_users_rss(self):
        res = self.app.get('/rss/users/',
                           headers=dict(accept='application/atom+xml'))
        self.assertIn('application/rss+xml', res.headers['Content-Type'])
        self.assertIn('bodhi', res)
        self.assertIn('guest', res)
        # check to catch performance regressions
        self.assertEquals(len(self.sql_statements), 3)

    def test_search_users(self):
        res = self.app.get('/users/', {'like': 'odh'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)

        user = body['users'][0]
        self.assertEquals(user['name'], u'bodhi')

        res = self.app.get('/users/', {'like': 'wat'})
        body = res.json_body
        self.assertEquals(len(body['users']), 0)

    def test_list_users_with_pagination(self):
        res = self.app.get('/users/')
        body = res.json_body
        self.assertEquals(len(body['users']), 3)

        users = [user['name'] for user in body['users']]

        res = self.app.get('/users/', {'rows_per_page': 1})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertIn(body['users'][0]['name'], users)

        res = self.app.get('/users/', {'rows_per_page': 1, 'page': 2})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertIn(body['users'][0]['name'], users)

        res = self.app.get('/users/', {'rows_per_page': 1, 'page': 3})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertIn(body['users'][0]['name'], users)

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
        update = self.db.query(Update).first()
        update.alias = u'some_alias'
        self.db.flush()

        res = self.app.get('/users/', {"updates": 'some_alias'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_nonexistant_update(self):
        res = self.app.get('/users/', {"updates": 'carbunkle'}, status=400)
        body = res.json_body
        self.assertEquals(body['errors'][0]['name'], 'updates')
        self.assertEquals(body['errors'][0]['description'],
                          'Invalid updates specified: carbunkle')

    def test_list_users_by_package_name(self):
        res = self.app.get('/users/', {"packages": 'bodhi'})
        body = res.json_body
        self.assertEquals(len(body['users']), 1)
        self.assertEquals(body['users'][0]['name'], 'guest')

    def test_list_users_by_nonexistant_package(self):
        res = self.app.get('/users/', {"packages": 'carbunkle'}, status=400)
        body = res.json_body
        self.assertEquals(body['errors'][0]['name'], 'packages')
        self.assertEquals(body['errors'][0]['description'],
                          'Invalid packages specified: carbunkle')
