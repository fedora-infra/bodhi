from pyramid import testing
from zope.interface import interfaces
import pytest

from bodhi.server import models
from bodhi.server.auth.utils import remember_me

from .. import base


class TestRememberMe(base.BasePyTestCase):
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
        assert models.User.get('lmacken') is None
        assert models.Group.get('releng') is None

        return req, info

    def test_bad_endpoint(self):
        """Test the post-login hook with a bad openid endpoint"""
        req, info = self._generate_req_info('bad_endpoint')

        with pytest.raises(interfaces.ComponentLookupError):
            remember_me(None, req, info)

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
