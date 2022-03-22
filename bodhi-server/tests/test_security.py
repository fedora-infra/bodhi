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

from cornice import errors
from pyramid import testing

from bodhi.server import security

from . import base


try:
    # Pyramid >= 2.0
    from pyramid.authorization import ALL_PERMISSIONS, Allow, DENY_ALL
except ImportError:
    # Pyramid < 2.0
    from pyramid.security import ALL_PERMISSIONS, Allow, DENY_ALL


class TestACLFactory:
    """Test the ACLFactory object."""

    def test___init__(self):
        """Ensure correct operation of the __init__() method."""
        r = testing.DummyRequest()

        f = security.ACLFactory(r)

        assert f.request is r


class TestAdminACLFactory(base.BasePyTestCase):
    """Test the AdminACLFactory object."""

    def test___acl__(self):
        """Test correct return value from the __acl__() method."""
        r = testing.DummyRequest()
        r.registry.settings = {'admin_groups': ['cool_gals', 'cool_guys']}
        f = security.AdminACLFactory(r)

        acls = f.__acl__()

        assert acls == (
            [(Allow, 'group:cool_gals', ALL_PERMISSIONS),
             (Allow, 'group:cool_guys', ALL_PERMISSIONS)] + [DENY_ALL])


class FakeRegistry(object):
    def __init__(self):
        self.settings = {'cors_origins_ro': 'origin_1,origin_2'}


@mock.patch('bodhi.server.security.get_current_registry',
            mock.MagicMock(return_value=FakeRegistry()))
class TestCorsOrigins:
    """Test the CorsOrigins class."""

    def test___contains___initialized(self):
        """Test __contains__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            assert 'origin_2' in co

    def test___contains___uninitialized(self):
        """Test __contains__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        assert 'origin_1' in co

    def test___getitem___initialized(self):
        """Test __getitem__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            assert co[1] == 'origin_2'

    def test___getitem___uninitialized(self):
        """Test __getitem__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        assert co[0] == 'origin_1'

    def test___init__(self):
        """Test correct behavior from __init__()."""
        co = security.CorsOrigins('cors_origins_ro')

        assert co.name == 'cors_origins_ro'
        assert co.origins is None

    def test___iter___initialized(self):
        """Test __iter__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            assert list(co) == ['origin_1', 'origin_2']

    def test___iter___uninitialized(self):
        """Test __iter__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        assert list(co) == ['origin_1', 'origin_2']

    def test___len___initialized(self):
        """Test __len__() when the origins are initialized."""
        co = security.CorsOrigins('cors_origins_ro')
        co.initialize()

        with mock.patch('bodhi.server.security.get_current_registry', side_effect=Exception()):
            # This should not raise the Exception because initialize() won't get called again.
            assert len(co) == 2

    def test___len___uninitialized(self):
        """Test __len__() when the origins are uninitialized."""
        co = security.CorsOrigins('cors_origins_ro')

        assert len(co) == 2

    def test_initialize_setting_not_found(self):
        """initialize() should set origins to ['localhost'] if the setting doesn't exist."""
        co = security.CorsOrigins('not_found')

        assert list(co) == ['localhost']

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

        assert co.origins == ['origin_1', 'origin_2']


class TestPackagerACLFactory(base.BasePyTestCase):
    """Test the PackagerACLFactory object."""

    def test___acl__(self):
        """Test correct return value from the __acl__() method."""
        r = testing.DummyRequest()
        r.registry.settings = {'mandatory_packager_groups': ['cool_gals', 'cool_guys']}
        f = security.PackagerACLFactory(r)

        acls = f.__acl__()

        assert acls == (
            [(Allow, 'group:cool_gals', ALL_PERMISSIONS),
             (Allow, 'group:cool_guys', ALL_PERMISSIONS)] + [DENY_ALL])


class TestProtectedRequest:
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
            assert getattr(pr, attr) == getattr(request, attr)

        assert isinstance(pr.errors, errors.Errors)
        assert pr.real_request is request
        assert not hasattr(pr, 'dontcopy')
