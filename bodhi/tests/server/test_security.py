# -*- coding: utf-8 -*-
# Copyright 2014-2017 Red Hat, Inc. and others.
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
"""Test the bodhi.server.security module."""

from pyramid.testing import DummyRequest
from zope.interface import interfaces

from bodhi.server import models, security
from bodhi.tests.server import base


class TestLogin(base.BaseTestCase):
    """Test the login() function."""
    def test_login(self):
        """Test the login redirect"""
        resp = self.app.get('/login', status=302)
        self.assertIn('dologin.html', resp)


class TestLogout(base.BaseTestCase):
    """Test the logout() function."""
    def test_logout(self):
        """Test the logout redirect"""
        resp = self.app.get('/logout', status=302)
        self.assertEquals(resp.location, 'http://localhost/')


class TestRememberMe(base.BaseTestCase):
    """Test the remember_me() function."""

    def _generate_req_info(self, openid_endpoint):
        """Generate the request and info to be handed to remember_me() for these tests."""
        req = DummyRequest(params={'openid.op_endpoint': openid_endpoint})
        req.db = self.db
        req.session['came_from'] = '/'
        info = {
            'identity_url': 'http://lmacken.id.fedoraproject.org',
            'groups': [u'releng'],
            'sreg': {'email': u'lmacken@fp.o'},
        }
        req.registry.settings = self.app_settings
        # Ensure the user doesn't exist yet
        self.assertIsNone(models.User.get(u'lmacken', self.db))
        self.assertIsNone(models.Group.get(u'releng', self.db))

        return req, info

    def test_bad_endpoint(self):
        """Test the post-login hook with a bad openid endpoint"""
        req, info = self._generate_req_info('bad_endpoint')

        with self.assertRaises(interfaces.ComponentLookupError):
            security.remember_me(None, req, info)

        # The user should not exist
        self.assertIsNone(models.User.get(u'lmacken', self.db))

    def test_new_user(self):
        """Test the post-login hook"""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])

        security.remember_me(None, req, info)

        # The user should now exist, and be a member of the releng group
        user = models.User.get(u'lmacken', self.db)
        self.assertEquals(user.name, u'lmacken')
        self.assertEquals(user.email, u'lmacken@fp.o')
        self.assertEquals(len(user.groups), 1)
        self.assertEquals(user.groups[0].name, u'releng')

    def test_user_groups_removed(self):
        """Test that a user that has been removed from a group gets marked as removed upon login."""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])
        security.remember_me(None, req, info)
        # Pretend the user has been removed from the releng group
        info['groups'] = []
        req.session = {'came_from': '/'}

        security.remember_me(None, req, info)

        user = models.User.get(u'lmacken', self.db)
        self.assertEquals(len(user.groups), 0)
        self.assertEquals(len(models.Group.get(u'releng', self.db).users), 0)
