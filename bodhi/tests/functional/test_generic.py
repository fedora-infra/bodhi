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

from bodhi.security import remember_me
from bodhi.models import DBSession, User, Group

from pyramid.testing import DummyRequest


class TestGenericViews(bodhi.tests.functional.base.BaseWSGICase):

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
        db = DBSession()
        req = DummyRequest(params={
            'openid.op_endpoint': self.app_settings['openid.provider'],
        })
        req.db = db
        req.session = {'came_from': '/'}
        info = {
            'identity_url': 'http://lmacken.id.fedoraproject.org',
            'groups': [u'releng'],
        }
        req.registry.settings = self.app_settings

        # Ensure the user doesn't exist yet
        self.assertIsNone(User.get(u'lmacken', db))
        self.assertIsNone(Group.get(u'releng', db))

        resp = remember_me(None, req, info)

        # The user should now exist, and be a member of the releng group
        user = User.get(u'lmacken', db)
        self.assertEquals(user.name, u'lmacken')
        self.assertEquals(len(user.groups), 1)
        self.assertEquals(user.groups[0].name, u'releng')

        # Pretend the user has been removed from the releng group
        info['groups'] = []
        req.session = {'came_from': '/'}

        resp = remember_me(None, req, info)

        user = User.get(u'lmacken', db)
        self.assertEquals(len(user.groups), 0)
        self.assertEquals(len(Group.get(u'releng', db).users), 0)


    def test_remember_me_with_bad_endpoint(self):
        """Test the post-login hook with a bad openid endpoint"""
        db = DBSession()
        req = DummyRequest(params={
            'openid.op_endpoint': 'bad_endpoint',
        })
        req.db = db
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
        self.assertIsNone(User.get(u'lmacken', db))

    def test_home(self):
        res = self.app.get('/', status=200)
        self.assertIn('Logout', res)
        self.assertIn('Fedora Update System', res)

    def test_markdown(self):
        res = self.app.get('/markdown', {'text': 'wat'}, status=200)
        self.assertEquals(res.json_body['html'], '<p>wat</p>')

    def test_markdown_with_html(self):
        res = self.app.get('/markdown', {'text': '<b>bold</b>'}, status=200)
        self.assertEquals(res.json_body['html'], '<p>--RAW HTML NOT ALLOWED--bold--RAW HTML NOT ALLOWED--</p>')

    def test_metrics(self):
        res = self.app.get('/metrics')
        self.assertIn('$.plot', res)
