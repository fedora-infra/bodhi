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
"""This test suite contains tests for bodhi.server.bugs."""

import unittest

from bodhi.server import bugs


class TestBugzilla(unittest.TestCase):
    """This test class contains tests for the Bugzilla class."""
    def test___init__(self):
        """Assert that the __init__ method sets up the Bugzilla object correctly."""
        bz = bugs.Bugzilla()

        self.assertIsNone(bz._bz)
