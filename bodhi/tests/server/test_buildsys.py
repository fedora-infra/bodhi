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
"""This test suite contains tests for the bodhi.server.buildsys module."""

import unittest

import koji
import mock

from bodhi.server import buildsys


class TestBuildsystem(unittest.TestCase):
    """This test class contains tests for the Buildsystem class."""
    def test_raises_not_implemented(self):
        """
        TheBuildsystem class is meant to be a superclass, so each of its methods raise
        NotImplementedError. Ensure that this is raised.
        """
        bs = buildsys.Buildsystem()

        for method in (
                bs.getBuild, bs.getLatestBuilds, bs.moveBuild, bs.ssl_login, bs.listBuildRPMs,
                bs.listTags, bs.listTagged, bs.taskFinished, bs.tagBuild, bs.untagBuild,
                bs.multiCall, bs.getTag):
            self.assertRaises(NotImplementedError, method)


class TestGetKrbConf(unittest.TestCase):
    """This class contains tests for the get_krb_conf() function."""
    def test_all_config_items_missing(self):
        """Assert behavior when all config items are missing."""
        config = {'some_meaningless_other_key': 'boring_value'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {})

    def test_complete_config(self):
        """Assert behavior with a config that has all possible elements."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config,
                         {'ccache': 'a_ccache', 'keytab': 'a_keytab', 'principal': 'a_principal'})

    def test_krb_ccache(self):
        """Assert behavior when only krb_ccache is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {'ccache': 'a_ccache'})

    def test_krb_keytab(self):
        """Assert behavior when only krb_keytab is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_keytab': 'a_keytab'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {'keytab': 'a_keytab'})

    def test_krb_principal(self):
        """Assert behavior when only krb_prinicpal is present."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_principal': 'a_principal'}

        config = buildsys.get_krb_conf(config)

        self.assertEqual(config, {'principal': 'a_principal'})


class TestKojiLogin(unittest.TestCase):
    """This class contains tests for the koji_login() function."""
    # krb_login returns a bool to indicate success or failure
    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.krb_login',
                mock.MagicMock(return_value=False))
    @mock.patch('bodhi.server.buildsys.log.error')
    def test_login_failure(self, error):
        """Assert correct behavior for a failed login event."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}

        client = buildsys.koji_login(config)

        self.assertEqual(type(client), koji.ClientSession)
        error.assert_called_once_with('Koji krb_login failed')

    # krb_login returns a bool to indicate success or failure
    @mock.patch.object(buildsys, '_koji_hub', 'http://example.com/koji')
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.krb_login',
                mock.MagicMock(return_value=True))
    @mock.patch('bodhi.server.buildsys.log.error')
    def test_login_success(self, error):
        """Assert correct behavior for a successful login event."""
        config = {'some_meaningless_other_key': 'boring_value', 'krb_ccache': 'a_ccache',
                  'krb_keytab': 'a_keytab', 'krb_principal': 'a_principal'}

        client = buildsys.koji_login(config)

        self.assertEqual(type(client), koji.ClientSession)
        # No error should have been logged
        self.assertEqual(error.call_count, 0)
