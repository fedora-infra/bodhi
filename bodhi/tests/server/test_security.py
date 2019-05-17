# Copyright 2014-2019 Red Hat, Inc. and others.
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

from unittest import mock
import unittest

from cornice import errors
from pyramid import testing
from pyramid.security import Allow, ALL_PERMISSIONS, DENY_ALL
from zope.interface import interfaces

from bodhi.server import models, security
from bodhi.tests.server import base


class TestACLFactory(unittest.TestCase):
    """Test the ACLFactory object."""

    def test___init__(self):
        """Ensure correct operation of the __init__() method."""
        r = testing.DummyRequest()

        f = security.ACLFactory(r)

        self.assertTrue(f.request is r)


class TestAdminACLFactory(base.BaseTestCase):
    """Test the AdminACLFactory object."""

    def test___acl__(self):
        """Test correct return value from the __acl__() method."""
        r = testing.DummyRequest()
        r.registry.settings = {'admin_groups': ['cool_gals', 'cool_guys']}
        f = security.AdminACLFactory(r)

        acls = f.__acl__()

        self.assertEqual(
            acls,
            [(Allow, 'group:cool_gals', ALL_PERMISSIONS),
             (Allow, 'group:cool_guys', ALL_PERMISSIONS)] + [DENY_ALL])


class FakeRegistry(object):
    def __init__(self):
        self.settings = {'cors_origins_ro': 'origin_1,origin_2'}


@mock.patch('bodhi.server.security.get_current_registry',
            mock.MagicMock(return_value=FakeRegistry()))
class TestCorsOrigins(unittest.TestCase):
    """Test the CorsOrigins class."""

    def test___contains___initialized(self):
        """Test __contains__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            self.assertTrue('origin_2' in co)

    def test___contains___uninitialized(self):
        """Test __contains__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        self.assertTrue('origin_1' in co)

    def test___getitem___initialized(self):
        """Test __getitem__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            self.assertEqual(co[1], 'origin_2')

    def test___getitem___uninitialized(self):
        """Test __getitem__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        self.assertEqual(co[0], 'origin_1')

    def test___init__(self):
        """Test correct behavior from __init__()."""
        co = security.CorsOrigins('cors_origins_ro')

        self.assertEqual(co.name, 'cors_origins_ro')
        self.assertIs(co.origins, None)

    def test___iter___initialized(self):
        """Test __iter__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            self.assertEqual(list(co), ['origin_1', 'origin_2'])

    def test___iter___uninitialized(self):
        """Test __iter__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        self.assertEqual(list(co), ['origin_1', 'origin_2'])

    def test___len___initialized(self):
        """Test __len__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            self.assertEqual(len(co), 2)

    def test___len___uninitialized(self):
        """Test __len__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        self.assertEqual(len(co), 2)

    def test_initialize_setting_not_found(self):
        """initialize() should set origins to ['localhost'] if the setting doesn't exist."""
        co = security.CorsOrigins('not_found')

        self.assertEqual(list(co), ['localhost'])

    def test_initialize_with_origins(self):
        """initialize() with origins already set should do nothing."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            co.initialize()

    def test_initialize_without_origins(self):
        """initialize() without origins set should set the origins."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        self.assertEqual(co.origins, ['origin_1', 'origin_2'])


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
        self.assertEqual(resp.location, 'http://localhost/')


class TestPackagerACLFactory(base.BaseTestCase):
    """Test the PackagerACLFactory object."""

    def test___acl__(self):
        """Test correct return value from the __acl__() method."""
        r = testing.DummyRequest()
        r.registry.settings = {'mandatory_packager_groups': ['cool_gals', 'cool_guys']}
        f = security.PackagerACLFactory(r)

        acls = f.__acl__()

        self.assertEqual(
            acls,
            [(Allow, 'group:cool_gals', ALL_PERMISSIONS),
             (Allow, 'group:cool_guys', ALL_PERMISSIONS)] + [DENY_ALL])


class TestProtectedRequest(unittest.TestCase):
    """Test the ProtectedRequest class."""
    def test___init__(self):
        """Assert that __init__() properly shadows the given Request."""
        request = testing.DummyRequest()
        request.buildinfo = mock.MagicMock()
        request.db = mock.MagicMock()
        request.user = mock.MagicMock()
        request.validated = mock.MagicMock()
        # This one shouldn't get copied.
        request.dontcopy = mock.MagicMock()

        pr = security.ProtectedRequest(request)

        for attr in ('db', 'registry', 'validated', 'buildinfo', 'user'):
            self.assertEqual(getattr(pr, attr), getattr(request, attr))

        self.assertTrue(isinstance(pr.errors, errors.Errors))
        self.assertTrue(pr.real_request is request)
        self.assertFalse(hasattr(pr, 'dontcopy'))


class TestRememberMe(base.BaseTestCase):
    """Test the remember_me() function."""

    def _generate_req_info(self, openid_endpoint):
        """Generate the request and info to be handed to remember_me() for these tests."""
        req = testing.DummyRequest(params={'openid.op_endpoint': openid_endpoint})
        req.db = self.db
        req.session['came_from'] = '/'
        info = {
            'identity_url': 'http://lmacken.id.fedoraproject.org',
            'groups': ['releng'],
            'sreg': {'email': 'lmacken@fp.o', 'nickname': 'lmacken'},
        }
        req.registry.settings = self.app_settings
        # Ensure the user doesn't exist yet
        self.assertIsNone(models.User.get('lmacken'))
        self.assertIsNone(models.Group.get('releng'))

        return req, info

    def test_bad_endpoint(self):
        """Test the post-login hook with a bad openid endpoint"""
        req, info = self._generate_req_info('bad_endpoint')

        with self.assertRaises(interfaces.ComponentLookupError):
            security.remember_me(None, req, info)

        # The user should not exist
        self.assertIsNone(models.User.get('lmacken'))

    def test_empty_groups_ignored(self):
        """Test a user that has an empty string group, which should be ignored."""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])
        security.remember_me(None, req, info)
        # Pretend the user has been removed from the releng group
        info['groups'] = ['releng', '', 'new_group']
        req.session = {'came_from': '/'}

        security.remember_me(None, req, info)

        user = models.User.get('lmacken')
        self.assertEqual([g.name for g in user.groups], ['releng', 'new_group'])

    def test_new_email(self):
        """Assert that the user gets their e-mail address updated."""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])
        security.remember_me(None, req, info)
        # The user has updated their e-mail address.
        info['sreg']['email'] = '1337hax0r@example.com'
        req.session = {'came_from': '/'}

        security.remember_me(None, req, info)

        user = models.User.get('lmacken')
        self.assertEqual(user.email, '1337hax0r@example.com')

    def test_new_user(self):
        """Test the post-login hook"""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])

        security.remember_me(None, req, info)

        # The user should now exist, and be a member of the releng group
        user = models.User.get('lmacken')
        self.assertEqual(user.name, 'lmacken')
        self.assertEqual(user.email, 'lmacken@fp.o')
        self.assertEqual(len(user.groups), 1)
        self.assertEqual(user.groups[0].name, 'releng')

    def test_user_groups_removed(self):
        """Test that a user that has been removed from a group gets marked as removed upon login."""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])
        security.remember_me(None, req, info)
        # Pretend the user has been removed from the releng group
        info['groups'] = []
        req.session = {'came_from': '/'}

        security.remember_me(None, req, info)

        user = models.User.get('lmacken')
        self.assertEqual(len(user.groups), 0)
        self.assertEqual(len(models.Group.get('releng').users), 0)
