# Copyright © 2016-2019 Red Hat, Inc. and others.
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
This module contains tests for the bodhi.server.tasks.clean_old_composes module.
"""

from unittest.mock import patch
import os
import shutil
import tempfile

from bodhi.server import config
from bodhi.server.tasks import clean_old_composes_task
from bodhi.server.tasks.clean_old_composes import main as clean_old_composes_main
from ..base import BasePyTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.bugs")
    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.clean_old_composes.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys, bugs):
        clean_old_composes_task(42)
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        bugs.set_bugtracker.assert_called_with()
        main_function.assert_called_with(42)


class TestMain(BasePyTestCase):
    """
    This class contains tests for the main() function.
    """

    def setup_method(self, method):
        super().setup_method(method)
        self.compose_dir = tempfile.mkdtemp()

    def teardown_method(self, method):
        shutil.rmtree(self.compose_dir)
        super().teardown_method(method)

    @patch('bodhi.server.tasks.clean_old_composes.log')
    def test_main(self, log):
        """
        Assert that clean_up removes the correct items and leaves the rest in place.
        """
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
        [os.makedirs(os.path.join(self.compose_dir, d)) for d in dirs]
        # Now let's make a few files here and there.
        with open(os.path.join(self.compose_dir, 'dist-5E-epel-161003.0724', 'oops.txt'),
                  'w') as oops:
            oops.write('This compose failed to get cleaned and left this file around, oops!')
        with open(os.path.join(self.compose_dir, 'COOL_FILE.txt'), 'w') as cool_file:
            cool_file.write('This file should be allowed to hang out here because it\'s cool.')
        with patch.dict(config.config, {'compose_dir': self.compose_dir}):
            clean_old_composes_main(2)
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
        actual_dirs = set([d for d in os.listdir(self.compose_dir)
                           if os.path.isdir(os.path.join(self.compose_dir, d))])
        assert actual_dirs == expected_dirs
        # The cool file should still be here
        actual_files = [f for f in os.listdir(self.compose_dir)
                        if os.path.isfile(os.path.join(self.compose_dir, f))]
        assert actual_files == ['COOL_FILE.txt']
        # Make sure the logged output is correct
        expected_output = set(dirs) - expected_dirs
        expected_output = {os.path.join(self.compose_dir, d) for d in expected_output}
        expected_output = expected_output | {'Deleting the following directories:'}
        logged = set([c[0][0] for c in log.info.call_args_list])
        assert logged == expected_output
