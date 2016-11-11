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
This module contains tests for the bodhi.server.scripts.untag_branched module.
"""
from cStringIO import StringIO

from mock import patch

from bodhi.server.scripts import untag_branched
from bodhi.tests.server.base import BaseTestCase


class TestUsage(BaseTestCase):
    """
    This class contains tests for the usage() function.
    """
    @patch('sys.exit')
    @patch('sys.stdout', new_callable=StringIO)
    def test_usage(self, stdout, exit):
        """
        Make sure the usage info is printed and then it exits.
        """
        argv = ['untag_branched']

        untag_branched.usage(argv)

        self.assertEqual(
            stdout.getvalue(),
            'usage: untag_branched <config_uri>\n(example: "untag_branched development.ini")\n')
        exit.assert_called_once_with(1)
