# Copyright © 2014-2019 Red Hat Inc. and others.
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

from bodhi.server.models import RpmBuild, RpmPackage
from .. import base


class TestBuildsService(base.BasePyTestCase):

    def test_404(self):
        self.app.get('/builds/a', status=404)

    def test_get_single_build(self):
        res = self.app.get('/builds/bodhi-2.0-1.fc17')
        assert res.json_body['nvr'] == 'bodhi-2.0-1.fc17'

    def test_list_builds(self):
        res = self.app.get('/builds/')
        body = res.json_body
        assert len(body['builds']) == 1

        up = body['builds'][0]
        assert up['nvr'] == 'bodhi-2.0-1.fc17'

    def test_list_builds_pagination(self):

        # First, stuff a second build in there
        session = self.db
        build = RpmBuild(nvr='bodhi-3.0-1.fc21',
                         package=RpmPackage.query.filter_by(name='bodhi').one())
        session.add(build)
        session.flush()

        # Then, test pagination
        res = self.app.get('/builds/', {"rows_per_page": 1})
        body = res.json_body
        assert len(body['builds']) == 1
        build1 = body['builds'][0]

        res = self.app.get('/builds/', {"rows_per_page": 1, "page": 2})
        body = res.json_body
        assert len(body['builds']) == 1
        build2 = body['builds'][0]

        assert build1 != build2

    def test_list_builds_by_package(self):
        res = self.app.get('/builds/', {"packages": "bodhi"})
        body = res.json_body
        assert len(body['builds']) == 1

        up = body['builds'][0]
        assert up['nvr'] == 'bodhi-2.0-1.fc17'

    def test_list_builds_by_nonexistent_package(self):
        res = self.app.get('/builds/', {"packages": "flash"}, status=400)
        assert res.json_body['errors'][0]['name'] == 'packages'
        assert res.json_body['errors'][0]['description'] == 'Invalid packages specified: flash'

    def test_list_builds_by_release_name(self):
        res = self.app.get('/builds/', {"releases": "F17"})
        body = res.json_body
        assert len(body['builds']) == 1

        up = body['builds'][0]
        assert up['nvr'] == 'bodhi-2.0-1.fc17'

    def test_list_builds_by_release_version(self):
        res = self.app.get('/builds/', {"releases": "17"})
        body = res.json_body
        assert len(body['builds']) == 1

        up = body['builds'][0]
        assert up['nvr'] == 'bodhi-2.0-1.fc17'

    def test_list_builds_by_nonexistent_release(self):
        res = self.app.get('/builds/', {"releases": "WinXP"}, status=400)
        assert res.json_body['errors'][0]['name'] == 'releases'
        assert res.json_body['errors'][0]['description'] == 'Invalid releases specified: WinXP'

    def test_list_builds_by_nvr(self):
        res = self.app.get('/builds/', {"nvr": "bodhi-2.0-1.fc17"})
        up = res.json_body['builds'][0]
        assert up['nvr'] == 'bodhi-2.0-1.fc17'

    def test_list_builds_by_update_alias(self):
        update = RpmBuild.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        res = self.app.get('/builds/', {"updates": [update.alias]})

        up = res.json_body['builds'][0]
        assert up['nvr'] == 'bodhi-2.0-1.fc17'

    def test_list_builds_no_rows_per_page(self):
        res = self.app.get('/builds/', {"rows_per_page": None}, status=400)
        assert res.json_body['status'] == 'error'
