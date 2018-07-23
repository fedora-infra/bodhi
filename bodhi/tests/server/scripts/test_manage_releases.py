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
import munch

from bodhi.server.scripts import manage_releases


EXAMPLE_RELEASE_MUNCH = munch.Munch({
    u'dist_tag': u'f27', u'name': u'F27', u'testing_tag': u'f27-updates-testing',
    u'pending_stable_tag': u'f27-updates-pending', u'pending_signing_tag': u'f27-signing-pending',
    u'long_name': u'Fedora 27', u'state': u'pending', u'version': u'27',
    u'override_tag': u'f27-override', u'branch': u'f27', u'id_prefix': u'FEDORA',
    u'pending_testing_tag': u'f27-updates-testing-pending', u'stable_tag': u'f27-updates',
    u'candidate_tag': u'f27-updates-candidate'})


EXPECTED_RELEASE_OUTPUT = """Saved release:
  Name:                F27
  Long Name:           Fedora 27
  Version:             27
  Branch:              f27
  ID Prefix:           FEDORA
  Dist Tag:            f27
  Stable Tag:          f27-updates
  Testing Tag:         f27-updates-testing
  Candidate Tag:       f27-updates-candidate
  Pending Signing Tag: f27-signing-pending
  Pending Testing Tag: f27-updates-testing-pending
  Pending Stable Tag:  f27-updates-pending
  Override Tag:        f27-override
  State:               pending
"""


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
