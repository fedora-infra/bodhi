# Copyright © 2018-2019 Sebastian Wojciechowski
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
"""
This module contains tests for the bodhi.server.scripts.bshell module.
"""

from unittest.mock import patch

from click import testing

from bodhi.server.scripts import bshell


class TestMain:
    """
    This class contains tests for the get_bodhi_shell() function.
    """
    @patch('bodhi.server.scripts.bshell.get_configfile')
    @patch('bodhi.server.scripts.bshell.call')
    def test_config_file_found(self, call, get_configfile):
        """Assert correct behavior when the config file exists"""
        get_configfile.return_value = "/path/to/config.ini"
        runner = testing.CliRunner()
        r = runner.invoke(bshell.get_bodhi_shell)

        assert r.exit_code == 0
        assert r.output == ""
        call.assert_called_once_with(['pshell-3', '/path/to/config.ini'])

    @patch('bodhi.server.scripts.bshell.get_configfile')
    @patch('bodhi.server.scripts.bshell.call')
    def test_config_file_not_found(self, call, get_configfile):
        """Assert correct behavior when the config file is not found"""
        get_configfile.return_value = None
        runner = testing.CliRunner()
        r = runner.invoke(bshell.get_bodhi_shell)

        assert r.exit_code == 1
        assert r.output == "Config file not found!\n"
        call.assert_not_called()
