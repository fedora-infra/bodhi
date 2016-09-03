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

import bodhi.tests.server.functional.base

from bodhi.server.security import remember_me
from bodhi.server.models import User, Group

from pyramid.testing import DummyRequest


class TestGenericViews(bodhi.tests.server.functional.base.BaseWSGICase):

    def test_login(self):
        """Test the login redirect"""
        resp = self.app.get('/login', status=302)
        self.assertIn('dologin.html', resp)

    def test_logout(self):
        """Test the logout redirect"""
        resp = self.app.get('/logout', status=302)
        self.assertEquals(resp.location, 'http://localhost/')

    def test_remember_me(self):
        """Test the post-login hook"""
        req = DummyRequest(params={
            'openid.op_endpoint': self.app_settings['openid.provider'],
        })
        req.db = self.db
        req.session = {'came_from': '/'}
        info = {
            'identity_url': 'http://lmacken.id.fedoraproject.org',
            'groups': [u'releng'],
            'sreg': {'email': u'lmacken@fp.o'},
        }
        req.registry.settings = self.app_settings

        # Ensure the user doesn't exist yet
        self.assertIsNone(User.get(u'lmacken', self.db))
        self.assertIsNone(Group.get(u'releng', self.db))

        resp = remember_me(None, req, info)

        # The user should now exist, and be a member of the releng group
        user = User.get(u'lmacken', self.db)
        self.assertEquals(user.name, u'lmacken')
        self.assertEquals(user.email, u'lmacken@fp.o')
        self.assertEquals(len(user.groups), 1)
        self.assertEquals(user.groups[0].name, u'releng')

        # Pretend the user has been removed from the releng group
        info['groups'] = []
        req.session = {'came_from': '/'}

        resp = remember_me(None, req, info)

        user = User.get(u'lmacken', self.db)
        self.assertEquals(len(user.groups), 0)
        self.assertEquals(len(Group.get(u'releng', self.db).users), 0)


    def test_remember_me_with_bad_endpoint(self):
        """Test the post-login hook with a bad openid endpoint"""
        req = DummyRequest(params={
            'openid.op_endpoint': 'bad_endpoint',
        })
        req.db = self.db
        def flash(msg):
            pass
        req.session.flash = flash
        info = {
            'identity_url': 'http://lmacken.id.fedoraproject.org',
            'groups': [u'releng'],
        }
        req.registry.settings = self.app_settings

        try:
            resp = remember_me(None, req, info)
            assert False, 'remember_me should have thrown an exception'
        except Exception:
            # A ComponentLookupError is thrown because we're doing this outside
            # of the webapp
            pass

        # The user should not exist
        self.assertIsNone(User.get(u'lmacken', self.db))

    def test_home(self):
        res = self.app.get('/', status=200)
        self.assertIn('Logout', res)
        self.assertIn('Fedora Update System', res)

    def test_markdown(self):
        res = self.app.get('/markdown', {'text': 'wat'}, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            "<p>wat</p>"
            "</div>"
        )

    def test_markdown_with_html(self):
        res = self.app.get('/markdown', {'text': '<b>bold</b>'}, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p>--RAW HTML NOT ALLOWED--bold--RAW HTML NOT ALLOWED--</p>'
            "</div>"
        )

    def test_markdown_with_mention(self):
        res = self.app.get('/markdown', {
            'text': 'my @colleague is distinguished',
        }, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p>my <a href="http://localhost/users/colleague">@colleague</a>'
            ' is distinguished</p>'
            "</div>"
        )

    def test_markdown_with_mention_at_start(self):
        res = self.app.get('/markdown', {
            'text': '@pingou is on it',
        }, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p><a href="http://localhost/users/pingou">@pingou</a>'
            ' is on it</p>'
            "</div>"
        )

    def test_markdown_with_mention_at_start_with_comma(self):
        res = self.app.get('/markdown', {
            'text': '@kevin, thanks for that',
        }, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p><a href="http://localhost/users/kevin">@kevin</a>'
            ', thanks for that</p>'
            "</div>"
        )

    def test_markdown_with_mention_with_numbers(self):
        res = self.app.get('/markdown', {
            'text': 'I vote for @number80',
        }, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p>I vote for '
            '<a href="http://localhost/users/number80">@number80</a></p>'
            "</div>"
        )

    def test_markdown_with_unprefixed_bugzilla(self):
        res = self.app.get('/markdown', {
            'text': 'Crazy.  #12345 is still busted.',
        }, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p>Crazy.  #12345 is still busted.</p>'
            "</div>"
        )

    def test_markdown_with_prefixed_bugzilla(self):
        res = self.app.get('/markdown', {
            'text': 'Crazy.  RHBZ#12345 is still busted.',
        }, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p>Crazy.  '
            '<a href="https://bugzilla.redhat.com/show_bug.cgi?id=12345">'
            '#12345</a> is still busted.</p>'
            "</div>"
        )

    def test_markdown_with_unknown_prefixed_bugzilla(self):
        res = self.app.get('/markdown', {
            'text': 'Crazy.  upstream#12345 is still busted.',
        }, status=200)
        self.assertEquals(
            res.json_body['html'],
            "<div class='markdown'>"
            '<p>Crazy.  upstream#12345 is still busted.</p>'
            "</div>"
        )

    def test_metrics(self):
        res = self.app.get('/metrics')
        self.assertIn('$.plot', res)

    def test_latest_builds(self):
        res = self.app.get('/latest_builds')
        body = res.json_body
        self.assertIn('f17-updates', body)
        self.assertIn('f17-updates-pending', body)
        self.assertIn('f17-updates-candidate', body)
        self.assertIn('f17-updates-testing', body)
        self.assertIn('f17-updates-testing-pending', body)
        self.assertIn('f17-override', body)
        self.assertEquals(body['f17-updates'], 'TurboGears-1.0.2.2-2.fc7')

    def test_version(self):
        res = self.app.get('/api_version')
        self.assertIn('version', res.json_body)
