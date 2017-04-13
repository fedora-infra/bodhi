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
"""This test suite enforces code style automatically."""

import os
import subprocess
import unittest


REPO_PATH = os.path.abspath(
    os.path.dirname(os.path.join(os.path.dirname(__file__), '..', '..', '..')))


class TestStyle(unittest.TestCase):
    """This test class contains tests pertaining to code style."""
    def test_code_with_flake8(self):
        """Enforce PEP-8 compliance on the codebase.

        This test runs flake8 on the code, and will fail if it returns a non-zero exit code.
        """
        # We ignore E712, which disallows non-identity comparisons with True and False
        flake8_command = ['flake8', '--max-line-length', '100', '--ignore=E712', REPO_PATH]

        self.assertEqual(subprocess.call(flake8_command), 0)

    @unittest.skipUnless(os.path.exists('/usr/bin/pydocstyle'),
                         'This test only runs if /usr/bin/pydocstyle exists.')
    def test_code_with_pydocstyle(self):
        """Enforce PEP-257 compliance on the codebase.

        This test runs pydocstyle on a subset of the code. The bodhi code is currently undergoing a
        change to bring all of the codebase into PEP-257 compliance, but the changes will be made
        slowly. This test enforces only modules that have been corrected to comply with pydocstyle.
        The goal is that this test would one day check the entire codebase.
        """
        enforced_paths = [
            'bodhi/server/scripts/__init__.py', 'bodhi/server/scripts/approve_testing.py',
            'bodhi/server/scripts/clean_old_mashes.py', 'bodhi/server/scripts/expire_overrides.py',
            'bodhi/server/scripts/initializedb.py']

        enforced_paths = [os.path.join(REPO_PATH, p) for p in enforced_paths]
        pydocstyle_command = ['pydocstyle']
        pydocstyle_command.extend(enforced_paths)

        self.assertEqual(subprocess.call(pydocstyle_command), 0)
