# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Red Hat, Inc.
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

import unittest

import mock

from bodhi.server.config import BodhiConfig


class BodhiConfigGetItemTests(unittest.TestCase):
    """Tests for the ``__getitem__`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``__getitem__`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual('hunter2', self.config['password'])
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``__getitem__`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual('hunter2', self.config['password'])
        self.assertEqual(0, self.config.load_config.call_count)

    def test_missing(self):
        """Assert you still get normal dictionary errors from the config."""
        self.assertRaises(KeyError, self.config.__getitem__, 'somemissingkey')


class BodhiConfigGetTests(unittest.TestCase):
    """Tests for the ``get`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``get`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual('hunter2', self.config.get('password'))
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``get`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual('hunter2', self.config.get('password'))
        self.assertEqual(0, self.config.load_config.call_count)

    def test_missing(self):
        """Assert you get ``None`` when the key is missing."""
        self.assertEqual(None, self.config.get('somemissingkey'))


class BodhiConfigPopItemTests(unittest.TestCase):
    """Tests for the ``pop`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``pop`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual('hunter2', self.config.pop('password'))
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``pop`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual('hunter2', self.config.pop('password'))
        self.assertEqual(0, self.config.load_config.call_count)

    def test_removes(self):
        """Assert the configuration is removed with ``pop``."""
        self.assertEqual('hunter2', self.config.pop('password'))
        self.assertRaises(KeyError, self.config.pop, 'password')

    def test_get_missing(self):
        """Assert you still get normal dictionary errors from the config."""
        self.assertRaises(KeyError, self.config.pop, 'somemissingkey')


class BodhiConfigCopyTests(unittest.TestCase):
    """Tests for the ``copy`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``copy`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual({'password': 'hunter2'}, self.config.copy())
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``copy`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual({'password': 'hunter2'}, self.config.copy())
        self.assertEqual(0, self.config.load_config.call_count)


class BodhiConfigLoadConfig(unittest.TestCase):

    @mock.patch('bodhi.server.config.get_configfile', mock.Mock(return_value='/some/config.ini'))
    @mock.patch('bodhi.server.config.get_appsettings')
    def test_marks_loaded(self, mock_appsettings):
        config = BodhiConfig()
        mock_appsettings.return_value = {'password': 'hunter2'}

        config.load_config()

        mock_appsettings.assert_called_once_with('/some/config.ini')
        self.assertEqual([('password', 'hunter2')], config.items())
        self.assertTrue(config.loaded)
