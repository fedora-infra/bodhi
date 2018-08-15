# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc.
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
"""This module contains tests for bodhi.server.scripts.manage_releases."""
import unittest

import mock

from bodhi.server.scripts import manage_releases
from bodhi.client import cli


class TestMain(unittest.TestCase):
    """
    Test the main() function.
    """
    @mock.patch('bodhi.client.releases')
    def test_main(self, releases):
        """
        Assert correct behavior when main() is called.
        """
        try:
            result = manage_releases.main()
            self.assertEqual(result, ("This utility has been deprecated. ",
                                      "Please use 'bodhi releases' instead."))
            releases.assert_called_once_with()
        except SystemExit:
            pass

    def test_consistent_username_option(self):
        """
        Assert consistency of '--username' option for `bodhi-manage-releases`
        after it's modification to '--user' in `bodhi releases`.
        """
        self.assertEqual(cli.commands['releases'].commands['create'].params[0].opts, ['--user'])
        self.assertEqual(cli.commands['releases'].commands['edit'].params[0].opts, ['--user'])

        try:
            manage_releases.main()
        except SystemExit:
            pass

        self.assertEqual(cli.commands['releases'].commands['create'].params[0].opts, ['--username'])
        self.assertEqual(cli.commands['releases'].commands['edit'].params[0].opts, ['--username'])
