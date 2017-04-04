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

import unittest

from bodhi import server
from bodhi.tests.server.functional import base


class TestMain(base.BaseWSGICase):
    """
    Assert correct behavior from the main() function.
    """
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
