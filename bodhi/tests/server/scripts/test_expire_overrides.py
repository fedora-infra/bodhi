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
"""
This module contains tests for the bodhi.server.scripts.expire_overrides module.
"""
import unittest

import mock

from bodhi.server.scripts import expire_overrides


class TestUsage(unittest.TestCase):
    """
    This class contains tests for the usage() function.
    """
    @mock.patch('sys.exit')
    @mock.patch('sys.stdout.write')
    def test_usage(self, write, exit):
        """
        Test that the right output and exit code are generated.
        """
        argv = ['/usr/bin/bodhi-expire-overrides']

        expire_overrides.usage(argv)

        message = ''.join([c[1][0] for c in write.mock_calls])
        self.assertEqual(
            message,
            ('usage: bodhi-expire-overrides <config_uri>\n(example: "bodhi-expire-overrides '
             'development.ini")\n'))
        exit.assert_called_once_with(1)
