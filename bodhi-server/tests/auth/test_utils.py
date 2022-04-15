from pyramid import testing
from pyramid.httpexceptions import HTTPUnauthorized
import pytest

from bodhi.server import models
from bodhi.server.auth.utils import get_final_redirect, remember_me

from .. import base


class TestRememberMe(base.BasePyTestCase):
    """Test the remember_me() function."""

    def setup_method(self, method):
        super().setup_method(method)
        # Declare the routes on the testing config, otherwise req.route_url() won't work.
        self.config.add_route('home', '/')
        self.config.include("bodhi.server.auth")

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
        assert models.User.get('lmacken') is None
        assert models.Group.get('releng') is None

        return req, info

    def test_bad_endpoint(self):
        """Test the post-login hook with a bad openid endpoint"""
        req, info = self._generate_req_info('bad_endpoint')

        with pytest.raises(HTTPUnauthorized) as exc:
            remember_me(None, req, info)

        assert str(exc.value) == (
            "Invalid OpenID provider. You can only use: https://id.stg.fedoraproject.org/openid/"
        )
        # The user should not exist
        assert models.User.get('lmacken') is None

    def test_empty_groups_ignored(self):
        """Test a user that has an empty string group, which should be ignored."""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])
        remember_me(None, req, info)
        # Pretend the user has been removed from the releng group
        info['groups'] = ['releng', '', 'new_group']
        req.session = {'came_from': '/'}

        remember_me(None, req, info)

        user = models.User.get('lmacken')
        assert [g.name for g in user.groups] == ['releng', 'new_group']

    def test_new_email(self):
        """Assert that the user gets their e-mail address updated."""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])
        remember_me(None, req, info)
        # The user has updated their e-mail address.
        info['sreg']['email'] = '1337hax0r@example.com'
        req.session = {'came_from': '/'}

        remember_me(None, req, info)

        user = models.User.get('lmacken')
        assert user.email == '1337hax0r@example.com'

    def test_new_user(self):
        """Test the post-login hook"""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])

        remember_me(None, req, info)

        # The user should now exist, and be a member of the releng group
        user = models.User.get('lmacken')
        assert user.name == 'lmacken'
        assert user.email == 'lmacken@fp.o'
        assert len(user.groups) == 1
        assert user.groups[0].name == 'releng'

    def test_user_groups_removed(self):
        """Test that a user that has been removed from a group gets marked as removed upon login."""
        req, info = self._generate_req_info(self.app_settings['openid.provider'])
        remember_me(None, req, info)
        # Pretend the user has been removed from the releng group
        info['groups'] = []
        req.session = {'came_from': '/'}

        remember_me(None, req, info)

        user = models.User.get('lmacken')
        assert len(user.groups) == 0
        assert len(models.Group.get('releng').users) == 0


class TestGetFinalRedirect(base.BasePyTestCase):
    """Test the get_final_redirect() function."""

    def setup_method(self, method):
        super().setup_method(method)
        # Declare the routes on the testing config, otherwise req.route_url() won't work.
        self.config.add_route('home', '/')
        self.config.include("bodhi.server.auth")

    def test_no_loop(self):
        """Make sure we don't redirect to the login page in a loop."""
        req = testing.DummyRequest()
        req.session['came_from'] = "http://example.com/login?method=openid"
        response = get_final_redirect(req)
        assert response.location == "/"
