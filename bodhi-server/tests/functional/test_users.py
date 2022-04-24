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

from bodhi.server.config import config
from bodhi.server.models import Update, User

from .. import base


class TestUsersService(base.BasePyTestCase):

    def setup_method(self, method):
        super(TestUsersService, self).setup_method(method)

        user = User(name='bodhi')
        self.db.add(user)
        self.db.flush()

    def test_404(self):
        self.app.get('/users/watwatwat', status=404)

    def test_get_single_user(self):
        res = self.app.get('/users/bodhi')
        assert res.json_body['user']['name'] == 'bodhi'

    def test_get_single_user_with_nonstandard_characters(self):
        """Test that we don't receive a 404 page with bot usernames."""
        user = User(name='bot/a.bad.name')
        self.db.add(user)
        self.db.flush()

        res = self.app.get('/users/bot/a.bad.name')
        assert res.json_body['user']['name'] == 'bot/a.bad.name'

    def test_get_hardcoded_avatar(self):
        res = self.app.get('/users/bodhi')
        assert res.json_body['user']['name'] == 'bodhi'
        url = 'https://apps.fedoraproject.org/img/icons/bodhi-24.png'
        assert res.json_body['user']['avatar'] == url

    def test_get_single_avatar(self):
        config["libravatar_enabled"] = True
        res = self.app.get('/users/guest')
        assert res.json_body['user']['name'] == 'guest'

        base = 'https://seccdn.libravatar.org/avatar/'
        h = 'eb48e08cc23bcd5961de9541ba5156c385cd39799e1dbf511477aa4d4d3a37e7'
        tail = '?d=retro&s=24'
        url = base + h

        assert res.json_body['user']['avatar'][:-len(tail)] == url

    def test_get_single_user_page(self):
        res = self.app.get('/users/guest', headers=dict(accept='text/html'))
        assert 'text/html' in res.headers['Content-Type']
        assert 'libravatar.org' in res
        assert '&copy;' in res

    def test_get_single_user_jsonp(self):
        res = self.app.get('/users/guest',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        assert 'application/javascript' in res.headers['Content-Type']
        assert 'libravatar.org' in res

    def test_get_single_user_rss(self):
        self.app.get('/users/bodhi',
                     headers=dict(accept='application/atom+xml'),
                     status=406)

    def test_list_users(self):
        res = self.app.get('/users/')
        assert 'application/json' in res.headers['Content-Type']
        body = res.json_body
        assert len(body['users']) == 3

        users = [user['name'] for user in body['users']]
        assert 'guest' in users
        assert 'anonymous' in users
        assert 'bodhi' in users

    def test_list_users_jsonp(self):
        res = self.app.get('/users/',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        assert 'application/javascript' in res.headers['Content-Type']
        assert 'callback' in res
        assert 'bodhi' in res
        assert 'guest' in res

    def test_list_users_rss(self):
        res = self.app.get('/rss/users/',
                           headers=dict(accept='application/atom+xml'))
        assert'application/rss+xml' in res.headers['Content-Type']
        assert'bodhi' in res
        assert'guest' in res

    def test_like_users(self):
        res = self.app.get('/users/', {'like': 'odh'})
        body = res.json_body
        assert len(body['users']) == 1

        user = body['users'][0]
        assert user['name'] == 'bodhi'

        res = self.app.get('/users/', {'like': 'wat'})
        body = res.json_body
        assert len(body['users']) == 0

    def test_search_users(self):
        """
        Test that the overrides/?search= endpoint works as expected
        """

        # test that search works
        res = self.app.get('/users/', {'search': 'bodh'})
        body = res.json_body
        assert len(body['users']) == 1
        user = body['users'][0]
        assert user['name'] == 'bodhi'

        # test that the search is case insensitive
        res = self.app.get('/users/', {'search': 'Bodh'})
        body = res.json_body
        assert len(body['users']) == 1
        user = body['users'][0]
        assert user['name'] == 'bodhi'

        # test a search that yields nothing
        res = self.app.get('/users/', {'search': 'wat'})
        body = res.json_body
        assert len(body['users']) == 0

    def test_list_users_with_pagination(self):
        res = self.app.get('/users/')
        body = res.json_body
        assert len(body['users']) == 3

        users = [user['name'] for user in body['users']]

        res = self.app.get('/users/', {'rows_per_page': 1})
        body = res.json_body
        assert len(body['users']) == 1
        assert body['users'][0]['name'] in users

        res = self.app.get('/users/', {'rows_per_page': 1, 'page': 2})
        body = res.json_body
        assert len(body['users']) == 1
        assert body['users'][0]['name'] in users

        res = self.app.get('/users/', {'rows_per_page': 1, 'page': 3})
        body = res.json_body
        assert len(body['users']) == 1
        assert body['users'][0]['name'] in users

    def test_list_users_by_name(self):
        res = self.app.get('/users/', {"name": 'guest'})
        body = res.json_body
        assert len(body['users']) == 1
        assert body['users'][0]['name'] == 'guest'

    def test_list_users_by_name_match(self):
        res = self.app.get('/users/', {"name": 'gue%'})
        body = res.json_body
        assert len(body['users']) == 1
        assert body['users'][0]['name'] == 'guest'

    def test_list_users_by_name_match_miss(self):
        res = self.app.get('/users/', {"name": '%wat%'})
        assert len(res.json_body['users']) == 0

    def test_list_users_by_groups(self):
        res = self.app.get('/users/', {"groups": 'packager'})
        assert len(res.json_body['users']) == 1

    def test_list_users_by_nonexistent_group(self):
        res = self.app.get('/users/', {"groups": 'carbunkle'}, status=400)
        body = res.json_body
        assert body['errors'][0]['name'] == 'groups'
        assert body['errors'][0]['description'] == 'Invalid groups specified: carbunkle'

    def test_list_users_by_mixed_nonexistent_group(self):
        res = self.app.get('/users/', {"groups": ['carbunkle', 'packager']}, status=400)
        body = res.json_body
        assert body['errors'][0]['name'] == 'groups'
        assert body['errors'][0]['description'] == 'Invalid groups specified: carbunkle'

    def test_list_users_by_group_miss(self):
        res = self.app.get('/users/', {"groups": 'provenpackager'})
        body = res.json_body
        assert len(body['users']) == 0
        assert 'errors' not in res.json_body

    def test_list_users_by_update_alias(self):
        update = self.db.query(Update).first()
        update.alias = 'some_alias'
        self.db.flush()

        res = self.app.get('/users/', {"updates": 'some_alias'})
        body = res.json_body
        assert len(body['users']) == 1
        assert body['users'][0]['name'] == 'guest'

    def test_list_users_by_nonexistent_update(self):
        res = self.app.get('/users/', {"updates": 'carbunkle'}, status=400)
        body = res.json_body
        assert body['errors'][0]['name'] == 'updates'
        assert body['errors'][0]['description'] == 'Invalid updates specified: carbunkle'
