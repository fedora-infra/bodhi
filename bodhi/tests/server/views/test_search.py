# Copyright 2017 Red Hat, Inc.
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
"""Contains tests for the bodhi.server.views.search module."""
import unittest

from bodhi.server import buildsys
from bodhi.server.views import search
from bodhi.tests.server import base


class TestGetAllPackages(unittest.TestCase):
    """Contains tests for the get_all_packages() function."""
    def setUp(self):
        """Set up the buildsys."""
        super(TestGetAllPackages, self).setUp()
        buildsys.setup_buildsystem({'buildsystem': 'dev'})

    def test_get_all_packages(self):
        """Assert correct operation of the function."""
        result = search.get_all_packages()

        self.assertEqual(result, ['nethack'])


class TestSearchPackages(base.BaseTestCase):
    """Contains tests for the search_packages() view."""
    def test_match(self):
        """Test with a parameter that matches."""
        resp = self.app.get('/search/packages', {'term': 'ethac'})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json_body,
                         [{'id': 'nethack', 'label': 'nethack', 'value': 'nethack'}])

    def test_unmatched(self):
        """Test with a search parameter that doesn't match anything."""
        resp = self.app.get('/search/packages', {'term': 'bodhi'})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json_body, [])
