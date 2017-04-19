# -*- coding: utf-8 -*-

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
"""This test suite contains tests for bodhi.server.__init__."""
import mock

from pyramid import authentication, authorization
import unittest

from bodhi import server
from bodhi.tests.server.functional import base


class TestMain(base.BaseWSGICase):
    """
    Assert correct behavior from the main() function.
    """
    @mock.patch('bodhi.server.Configurator.set_authentication_policy')
    @mock.patch('bodhi.server.Configurator.set_authorization_policy')
    def test_authtkt_timeout_defined(self, set_authorization_policy, set_authentication_policy):
        """Ensure that main() uses the setting when authtkt.timeout is defined in settings."""
        with mock.patch.dict(
                self.app_settings,
                {'authtkt.timeout': '10', 'authtkt.secret': 'hunter2', 'authtkt.secure': 'true'}):
            server.main({}, **self.app_settings)

        policy = set_authentication_policy.mock_calls[0][1][0]
        self.assertTrue(isinstance(policy, authentication.AuthTktAuthenticationPolicy))
        self.assertEqual(policy.callback, server.groupfinder)
        self.assertEqual(policy.cookie.hashalg, 'sha512')
        self.assertEqual(policy.cookie.max_age, 10)
        self.assertEqual(policy.cookie.secure, True)
        self.assertEqual(policy.cookie.secret, 'hunter2')
        self.assertEqual(policy.cookie.timeout, 10)
        set_authentication_policy.assert_called_once_with(policy)
        # Ensure that the ACLAuthorizationPolicy was used
        policy = set_authorization_policy.mock_calls[0][1][0]
        self.assertTrue(isinstance(policy, authorization.ACLAuthorizationPolicy))
        set_authorization_policy.assert_called_once_with(policy)

    @mock.patch('bodhi.server.Configurator.set_authentication_policy')
    @mock.patch('bodhi.server.Configurator.set_authorization_policy')
    def test_authtkt_timeout_undefined(self, set_authorization_policy, set_authentication_policy):
        """Ensure that main() uses a default if authtkt.timeout is undefined in settings."""
        with mock.patch.dict(
                self.app_settings, {'authtkt.secret': 'hunter2', 'authtkt.secure': 'true'}):
            server.main({}, **self.app_settings)

        policy = set_authentication_policy.mock_calls[0][1][0]
        self.assertTrue(isinstance(policy, authentication.AuthTktAuthenticationPolicy))
        self.assertEqual(policy.callback, server.groupfinder)
        self.assertEqual(policy.cookie.hashalg, 'sha512')
        self.assertEqual(policy.cookie.max_age, 86400)
        self.assertEqual(policy.cookie.secure, True)
        self.assertEqual(policy.cookie.secret, 'hunter2')
        self.assertEqual(policy.cookie.timeout, 86400)
        set_authentication_policy.assert_called_once_with(policy)
        # Ensure that the ACLAuthorizationPolicy was used
        policy = set_authorization_policy.mock_calls[0][1][0]
        self.assertTrue(isinstance(policy, authorization.ACLAuthorizationPolicy))
        set_authorization_policy.assert_called_once_with(policy)

    @mock.patch('bodhi.server.bugs.set_bugtracker')
    def test_calls_set_bugtracker(self, set_bugtracker):
        """
        Ensure that main() calls set_bugtracker().
        """
        server.main({}, testing='guest', session=self.db, **self.app_settings)

        set_bugtracker.assert_called_once_with()


class TestGetDbSessionForRequest(unittest.TestCase):

    def test_session_from_registry_sessionmaker(self):
        """Assert the session is created using the sessionmaker in the registry."""
        mock_request = mock.Mock()
        session = server.get_db_session_for_request(mock_request)
        mock_request.registry.sessionmaker.assert_called_once_with()
        self.assertEqual(session, mock_request.registry.sessionmaker.return_value)
