# Copyright © 2015-2019 Red Hat, Inc. and others.
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
from bodhi.server.models import (
    RpmPackage,
)
from .. import base


class TestRpmPackagesService(base.BasePyTestCase):
    def test_basic_json(self):
        """ Test querying with no arguments... """
        self.db.add(RpmPackage(name='a_second_package'))
        self.db.commit()
        resp = self.app.get('/packages/')
        body = resp.json_body
        assert len(body['packages']) == 2

    def test_filter_by_name(self):
        """ Test that filtering by name returns one package and not the other.
        """
        self.db.add(RpmPackage(name='a_second_package'))
        self.db.commit()
        resp = self.app.get('/packages/', dict(name='bodhi'))
        body = resp.json_body
        assert len(body['packages']) == 1

    def test_filter_by_like(self):
        """ Test that filtering by like returns one package and not the other.
        """
        self.db.add(RpmPackage(name='a_second_package'))
        self.db.commit()
        resp = self.app.get('/packages/', dict(like='odh'))
        body = resp.json_body
        assert len(body['packages']) == 1

    def test_filter_by_search(self):
        """ Test filtering by search
        """
        self.db.add(RpmPackage(name='a_second_package'))
        self.db.commit()

        # test search
        resp = self.app.get('/packages/', dict(search='bodh'))
        body = resp.json_body
        assert len(body['packages']) == 1

        # test the search is case-insensitive
        resp = self.app.get('/packages/', dict(search='Bodh'))
        body = resp.json_body
        assert len(body['packages']) == 1

        # test a search that yields nothing
        resp = self.app.get('/packages/', dict(search='corebird'))
        body = resp.json_body
        assert len(body['packages']) == 0
