# Copyright © 2007-2019 Red Hat, Inc. and others.
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
"""This test suite contains tests for bodhi.server.__init__."""
from unittest import mock
import collections
import unittest

from pyramid import authentication, authorization, testing
import munch

from bodhi import server
from bodhi.server import models
from bodhi.server.config import config
from bodhi.server.views import generic
from bodhi.tests.server import base


class TestExceptionFilter(unittest.TestCase):
    """Test the exception_filter() function."""
    @mock.patch('bodhi.server.log.exception')
    def test_exception(self, exception):
        """An Exception should be logged and returned."""
        request_response = OSError('Your money is gone.')

        # The second argument is not used.
        response = server.exception_filter(request_response, None)

        self.assertIs(response, request_response)
        exception.assert_called_once_with(
            "Unhandled exception raised:  {}".format(repr(request_response)))

    @mock.patch('bodhi.server.log.exception')
    def test_no_exception(self, exception):
        """A non-exception should not be logged and should be returned."""
        request_response = 'Your money is safe with me.'

        # The second argument is not used.
        response = server.exception_filter(request_response, None)

        self.assertIs(response, request_response)
        self.assertEqual(exception.call_count, 0)


class TestGetBuildinfo(unittest.TestCase):
    """Test get_buildinfo()."""
    def test_get_buildinfo(self):
        """get_buildinfo() should return an empty defaultdict."""
        # The argument isn't used, so we'll just pass None.
        bi = server.get_buildinfo(None)

        self.assertTrue(isinstance(bi, collections.defaultdict))
        self.assertEqual(bi, {})
        self.assertEqual(bi['made_up_key'], {})


class TestGetCacheregion(unittest.TestCase):
    """Test get_cacheregion()."""
    @mock.patch.dict('bodhi.server.bodhi_config', {'some': 'config'}, clear=True)
    @mock.patch('bodhi.server.make_region')
    def test_get_cacheregion(self, make_region):
        """Test get_cacheregion."""
        # The argument (request) doesn't get used, so we'll just pass None.
        region = server.get_cacheregion(None)

        make_region.assert_called_once_with()
        self.assertEqual(region, make_region.return_value)
        region.configure_from_config.assert_called_once_with({'some': 'config'}, 'dogpile.cache.')


class TestGetKoji(unittest.TestCase):
    """Test get_koji()."""
    @mock.patch('bodhi.server.buildsys.get_session')
    def test_get_koji(self, get_session):
        """Ensure that get_koji() returns the response from buildsys.get_session()."""
        # The argument is not used, so set it to None.
        k = server.get_koji(None)

        self.assertIs(k, get_session.return_value)


class TestGetReleases(base.BaseTestCase):
    """Test the get_releases() function."""
    def test_get_releases(self):
        """Assert correct return value from get_releases()."""
        request = testing.DummyRequest(user=base.DummyUser('guest'))

        releases = server.get_releases(request)

        self.assertEqual(releases, models.Release.all_releases())


class TestGetUser(base.BaseTestCase):
    """Test get_user()."""
    def test_authenticated(self):
        """Assert that a munch gets returned for an authenticated user."""
        db_user = models.User.query.filter_by(name='guest').one()

        class Request(object):
            """
            Fake a Request.

            We don't use the DummyRequest because it doesn't allow us to set the
            unauthenticated_user attribute. We don't use mock because it causes serialization
            problems with the call to user.__json__().
            """
            cache = mock.MagicMock()
            db = self.db
            registry = mock.MagicMock()
            unauthenticated_userid = db_user.name

        user = server.get_user(Request())

        self.assertEqual(user['groups'], [{'name': 'packager'}])
        self.assertEqual(user['name'], 'guest')
        self.assertTrue(isinstance(user, munch.Munch))

    def test_unauthenticated(self):
        """Assert that None gets returned for an unauthenticated user."""
        class Request(object):
            """
            Fake a Request.

            We don't use the DummyRequest because it doesn't allow us to set the
            unauthenticated_user attribute. We don't use mock because it causes serialization
            problems with the call to user.__json__().
            """
            cache = mock.MagicMock()
            db = self.db
            registry = mock.MagicMock()
            unauthenticated_userid = None

        user = server.get_user(Request())

        self.assertIsNone(user)


class TestGroupfinder(base.BaseTestCase):
    """Test the groupfinder() function."""

    def test_no_user(self):
        """Test when there is not a user."""
        request = testing.DummyRequest(user=base.DummyUser('guest'))
        request.db = self.db

        # The first argument isn't used, so just set it to None.
        groups = server.groupfinder(None, request)

        self.assertEqual(groups, ['group:packager'])

    def test_user(self):
        """Test with a user."""
        request = testing.DummyRequest(user=None)

        # The first argument isn't used, so just set it to None.
        self.assertIsNone(server.groupfinder(None, request))


class TestMain(base.BaseTestCase):
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

    def test_calls_session_remove(self):
        """Let's assert that main() calls Session.remove()."""
        with mock.patch('bodhi.server.Session.remove') as remove:
            server.main({}, **self.app_settings)

        remove.assert_called_once_with()

    @mock.patch('bodhi.server.bugs.set_bugtracker')
    def test_calls_set_bugtracker(self, set_bugtracker):
        """
        Ensure that main() calls set_bugtracker().
        """
        server.main({}, testing='guest', session=self.db, **self.app_settings)

        set_bugtracker.assert_called_once_with()

    @mock.patch.dict('bodhi.server.config.config', {'test': 'changeme'})
    def test_settings(self):
        """Ensure that passed settings make their way into the Bodhi config."""
        self.app_settings.update({'test': 'setting'})

        server.main({}, testing='guest', session=self.db, **self.app_settings)

        self.assertEqual(config['test'], 'setting')

    @mock.patch.dict(
        'bodhi.server.config.config',
        {'dogpile.cache.backend': 'dogpile.cache.memory', 'dogpile.cache.expiration_time': 100})
    @mock.patch('bodhi.server.views.generic._generate_home_page_stats', autospec=True)
    def test_sets_up_home_page_cache(self, _generate_home_page_stats):
        """Ensure that the home page cache is configured."""
        _generate_home_page_stats.return_value = 5
        # Let's pull invalidate off of the mock so that main() will decorate it again as a cache.
        del _generate_home_page_stats.invalidate
        self.assertFalse(hasattr(_generate_home_page_stats, 'invalidate'))

        server.main({}, testing='guest', session=self.db)

        # main() should have given it a cache, which would give it an invalidate attribute.
        self.assertTrue(hasattr(generic._generate_home_page_stats, 'invalidate'))
        self.assertEqual(generic._generate_home_page_stats(), 5)
        # Changing the return value of the mock should not affect the return value since it is
        # cached.
        _generate_home_page_stats.return_value = 7
        self.assertEqual(generic._generate_home_page_stats(), 5)
        # If we invalidate the cache, we should see the new return value.
        generic._generate_home_page_stats.invalidate()
        self.assertEqual(generic._generate_home_page_stats(), 7)

    @mock.patch.dict('bodhi.server.config.config', {'warm_cache_on_start': True})
    def test_warms_up_releases_cache(self):
        """main() should warm up the _all_releases cache."""
        # Let's force the release cache to None
        models.Release._all_releases = None

        server.main({}, testing='guest', session=self.db)

        # The cache should have a release in it now - let's just spot check it
        self.assertEqual(models.Release._all_releases['current'][0]['name'], 'F17')
