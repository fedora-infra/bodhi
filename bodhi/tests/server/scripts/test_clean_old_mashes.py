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
This module contains tests for the bodhi.server.scripts.clean_old_mashes module.
"""
import os
import shutil
import tempfile
import unittest

from click import testing
from mock import patch

from bodhi.server import config
from bodhi.server.scripts import clean_old_mashes


class TestCleanUp(unittest.TestCase):
    """
    This class contains tests for the clean_up() function.
    """
    @patch('bodhi.server.scripts.clean_old_mashes.NUM_TO_KEEP', 2)
    def test_clean_up(self):
        """
        Assert that clean_up removes the correct items and leaves the rest in place.
        """
        try:
            mash_dir = tempfile.mkdtemp()
            # Set up some directories that look similar to what might be found in production, with
            # some directories that don't match the pattern of ending in -<timestamp>.
            dirs = [
                'dist-5E-epel-161003.0724', 'dist-5E-epel-161011.0458', 'dist-5E-epel-161012.1854',
                'dist-5E-epel-161013.1711', 'dist-5E-epel-testing-161001.0424',
                'dist-5E-epel-testing-161003.0856', 'dist-5E-epel-testing-161006.0053',
                'dist-6E-epel-161002.2331', 'dist-6E-epel-161003.2046',
                'dist-6E-epel-testing-161001.0528', 'epel7-161003.0724', 'epel7-161003.2046',
                'epel7-161004.1423', 'epel7-161005.1122', 'epel7-testing-161001.0424',
                'epel7-testing-161003.0621', 'epel7-testing-161003.2217', 'f23-updates-161002.2331',
                'f23-updates-161003.1302', 'f23-updates-161004.1423', 'f23-updates-161005.0259',
                'f23-updates-testing-161001.0424', 'f23-updates-testing-161003.0621',
                'f23-updates-testing-161003.2217', 'f24-updates-161002.2331',
                'f24-updates-161003.1302', 'f24-updates-testing-161001.0424',
                'this_should_get_left_alone', 'f23-updates-should_be_untouched',
                'f23-updates.repocache', 'f23-updates-testing-blank']
            [os.makedirs(os.path.join(mash_dir, d)) for d in dirs]
            # Now let's make a few files here and there.
            with open(os.path.join(mash_dir, 'dist-5E-epel-161003.0724', 'oops.txt'), 'w') as oops:
                oops.write('This mash failed to get cleaned and left this file around, oops!')
            with open(os.path.join(mash_dir, 'COOL_FILE.txt'), 'w') as cool_file:
                cool_file.write('This file should be allowed to hang out here because it\'s cool.')

            with patch.dict(config.config, {'mash_dir': mash_dir}):
                result = testing.CliRunner().invoke(clean_old_mashes.clean_up, [])

            self.assertEqual(result.exit_code, 0)
            # We expect these and only these directories to remain.
            expected_dirs = {
                'dist-5E-epel-161012.1854', 'dist-5E-epel-161013.1711',
                'dist-5E-epel-testing-161003.0856', 'dist-5E-epel-testing-161006.0053',
                'dist-6E-epel-161002.2331', 'dist-6E-epel-161003.2046',
                'dist-6E-epel-testing-161001.0528', 'epel7-161004.1423', 'epel7-161005.1122',
                'epel7-testing-161003.0621', 'epel7-testing-161003.2217', 'f23-updates-161004.1423',
                'f23-updates-161005.0259', 'f23-updates-testing-161003.0621',
                'f23-updates-testing-161003.2217', 'f24-updates-161002.2331',
                'f24-updates-161003.1302', 'f24-updates-testing-161001.0424',
                'this_should_get_left_alone', 'f23-updates-should_be_untouched',
                'f23-updates.repocache', 'f23-updates-testing-blank'}
            actual_dirs = set([d for d in os.listdir(mash_dir)
                               if os.path.isdir(os.path.join(mash_dir, d))])
            self.assertEqual(actual_dirs, expected_dirs)
            # The cool file should still be here
            actual_files = [f for f in os.listdir(mash_dir)
                            if os.path.isfile(os.path.join(mash_dir, f))]
            self.assertEqual(actual_files, ['COOL_FILE.txt'])
            # Make sure the printed output is correct
            expected_output = set(dirs) - expected_dirs
            expected_output = {os.path.join(mash_dir, d) for d in expected_output}
            expected_output = expected_output | {'Deleting the following directories:', ''}
            self.assertEqual(set(result.output.split('\n')), expected_output)
        finally:
            shutil.rmtree(mash_dir)
