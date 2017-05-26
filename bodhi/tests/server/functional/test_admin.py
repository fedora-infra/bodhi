# Copyright 2017 Red Hat, Inc.
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

import copy

from webtest import TestApp

from bodhi.server import main
import bodhi.tests.server.functional.base


class TestAdminView(bodhi.tests.server.functional.base.BaseWSGICase):

    def test_admin(self):
        """Test that authticated user can see the Admin panel"""
        res = self.app.get('/admin/')
        body = res.json_body
        self.assertEquals(body['principals'][0], 'system.Everyone')
        self.assertEquals(body['principals'][1], 'system.Authenticated')
        self.assertEquals(body['principals'][2], 'guest')
        self.assertEquals(body['user'], 'guest')

    def test_admin_unauthed(self):
        """Test that an unauthed user cannot see the admin endpoint"""
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/admin/', status=403)
        self.assertIn('<h1>403 <small>Forbidden</small></h1>', res)
        self.assertIn('<p class="lead">Access was denied to this resource.</p>', res)
