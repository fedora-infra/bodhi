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
"""This test suite contains tests for the bodhi.server.consumers.updates module."""

import copy
import unittest

import mock

from bodhi.server import util
from bodhi.server.consumers import updates


class TestUpdatesHandlerInit(unittest.TestCase):
    """This test class contains tests for the UpdatesHandler.__init__() method."""
    def test_handle_bugs_bodhi_email_falsy(self):
        """
        Assert that bug handling is disabled when bodhi_email is configured "falsy".
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}

        with mock.patch.dict(updates.config, {'bodhi_email': ''}):
            h = updates.UpdatesHandler(hub)

        self.assertEqual(h.handle_bugs, False)

    def test_handle_bugs_bodhi_email_missing(self):
        """
        Assert that bug handling is disabled when bodhi_email is not configured.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}
        replacement_config = copy.deepcopy(updates.config)
        del replacement_config['bodhi_email']

        with mock.patch.dict(updates.config, replacement_config, clear=True):
            h = updates.UpdatesHandler(hub)

        self.assertEqual(h.handle_bugs, False)

    @mock.patch('bodhi.server.consumers.updates.fedmsg.consumers.FedmsgConsumer.__init__')
    def test_super___init___called(self, __init__):
        """
        Make sure the superclass's __init__() was called.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}

        with mock.patch.dict(updates.config, {'bodhi_email': 'bowlofeggs@fpo.org'}):
            h = updates.UpdatesHandler(hub)

        __init__.assert_called_once_with(hub)

    def test_typical_config(self):
        """
        Test the method with a typical config.
        """
        hub = mock.MagicMock()
        hub.config = {'environment': 'environment',
                      'topic_prefix': 'topic_prefix'}

        with mock.patch.dict(updates.config, {'bodhi_email': 'bowlofeggs@fpo.org'}):
            h = updates.UpdatesHandler(hub)

        self.assertEqual(h.handle_bugs, True)
        self.assertEqual(type(h.db_factory), util.TransactionalSessionMaker)
        self.assertEqual(
            h.topic,
            ['topic_prefix.environment.bodhi.update.request.testing',
             'topic_prefix.environment.bodhi.update.edit'])
