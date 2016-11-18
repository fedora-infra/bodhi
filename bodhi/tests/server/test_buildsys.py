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
"""This test suite contains tests for the bodhi.server.buildsys module."""

import unittest

from bodhi.server import buildsys


class TestBuildsystem(unittest.TestCase):
    """This test class contains tests for the Buildsystem class."""
    def test_raises_not_implemented(self):
        """
        TheBuildsystem class is meant to be a superclass, so each of its methods raise
        NotImplementedError. Ensure that this is raised.
        """
        bs = buildsys.Buildsystem()

        for method in (
                bs.getBuild, bs.getLatestBuilds, bs.moveBuild, bs.ssl_login, bs.listBuildRPMs,
                bs.listTags, bs.listTagged, bs.taskFinished, bs.tagBuild, bs.untagBuild,
                bs.multiCall, bs.getTag):
            self.assertRaises(NotImplementedError, method)
