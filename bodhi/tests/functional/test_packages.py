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


import bodhi.tests.functional.base

from bodhi.models import (
    Package,
)


class TestPackagesService(bodhi.tests.functional.base.BaseWSGICase):
    def test_basic_json(self):
        """ Test querying with no arguments... """
        self.db.add(Package(name='a_second_package'))
        resp = self.app.get('/packages/')
        body = resp.json_body
        self.assertEquals(len(body['packages']), 2)

    def test_filter_by_name(self):
        """ Test that filtering by name returns one package and not the other.
        """
        self.db.add(Package(name='a_second_package'))
        resp = self.app.get('/packages/', dict(name='bodhi'))
        body = resp.json_body
        self.assertEquals(len(body['packages']), 1)

    def test_filter_by_like(self):
        """ Test that filtering by like returns one package and not the other.
        """
        self.db.add(Package(name='a_second_package'))
        resp = self.app.get('/packages/', dict(like='odh'))
        body = resp.json_body
        self.assertEquals(len(body['packages']), 1)
