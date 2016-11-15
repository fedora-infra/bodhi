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
"""This test module contains tests for bodhi.server.notifications."""

import unittest

import mock

from bodhi.server import notifications


class TestInit(unittest.TestCase):
    """This test class contains tests for the init() function."""
    @mock.patch.dict('bodhi.server.config.config', {'fedmsg_enabled': True})
    @mock.patch('bodhi.server.log.info')
    @mock.patch('fedmsg.config.load_config')
    @mock.patch('fedmsg.init')
    def test_config_passed(self, init, load_config, info):
        """
        Assert that the config from load_config() is passed to init().
        """
        load_config.return_value = {'a': 'config'}
        notifications.init()

        init.assert_called_once_with(a='config')
        info.assert_called_once_with('fedmsg initialized')

    @mock.patch.dict('bodhi.server.config.config', {'fedmsg_enabled': False})
    @mock.patch('bodhi.server.log.warn')
    @mock.patch('bodhi.server.notifications.fedmsg.init')
    def test_fedmsg_disabled(self, init, warn):
        """
        The init() function should log a warning and exit when fedmsg is disabled.
        """
        notifications.init()

        # fedmsg.init() should not have been called
        self.assertEqual(init.call_count, 0)
        warn.assert_called_once_with('fedmsg disabled.  not initializing.')

    @mock.patch.dict('bodhi.server.config.config', {'fedmsg_enabled': True})
    @mock.patch('bodhi.server.log.info')
    @mock.patch('fedmsg.init')
    def test_with_active(self, init, info):
        """
        Assert correct behavior with active is not None.
        """
        notifications.init(active=True)

        self.assertEqual(init.call_count, 1)
        init_config = init.mock_calls[0][2]
        self.assertEqual(init_config['active'], True)
        self.assertEqual(init_config['name'], 'relay_inbound')
        self.assertTrue('cert_prefix' not in init_config)
        info.assert_called_once_with('fedmsg initialized')

    @mock.patch.dict('bodhi.server.config.config', {'fedmsg_enabled': True})
    @mock.patch('bodhi.server.log.info')
    @mock.patch('fedmsg.init')
    def test_with_cert_prefix(self, init, info):
        """
        Assert correct behavior when cert_prefix is not None.
        """
        notifications.init(cert_prefix='This is a real cert trust me.')

        self.assertEqual(init.call_count, 1)
        init_config = init.mock_calls[0][2]
        self.assertEqual(init_config['cert_prefix'], 'This is a real cert trust me.')
        info.assert_called_once_with('fedmsg initialized')
