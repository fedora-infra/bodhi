from datetime import datetime, timedelta
from webtest import TestApp

import bodhi.tests.functional.base

from bodhi import main
from bodhi.models import (
    Base,
    Bug,
    Build,
    CVE,
    DBSession,
    Group,
    Package,
    Release,
    Build,
    User,
)


class TestBuildsService(bodhi.tests.functional.base.BaseWSGICase):

    def test_404(self):
        self.app.get('/builds/a', status=404)

    def test_get_single_build(self):
        res = self.app.get('/builds/bodhi-2.0-1.fc17')
        self.assertEquals(res.json_body['nvr'], 'bodhi-2.0-1.fc17')

    def test_list_builds(self):
        res = self.app.get('/builds/')
        body = res.json_body
        self.assertEquals(len(body['builds']), 1)

        up = body['builds'][0]
        self.assertEquals(up['nvr'], u'bodhi-2.0-1.fc17')

    def test_list_builds_pagination(self):

        # First, stuff a second build in there
        session = DBSession()
        build = Build(nvr=u'bodhi-3.0-1.fc21')
        session.add(build)
        session.flush()

        # Then, test pagination
        res = self.app.get('/builds/', {"rows_per_page": 1})
        body = res.json_body
        self.assertEquals(len(body['builds']), 1)
        build1 = body['builds'][0]

        res = self.app.get('/builds/', {"rows_per_page": 1, "page": 2})
        body = res.json_body
        self.assertEquals(len(body['builds']), 1)
        build2 = body['builds'][0]

        self.assertNotEquals(build1, build2)


    def test_list_builds_by_package(self):
        res = self.app.get('/builds/', {"packages": "bodhi"})
        body = res.json_body
        self.assertEquals(len(body['builds']), 1)

        up = body['builds'][0]
        self.assertEquals(up['nvr'], u'bodhi-2.0-1.fc17')

    def test_list_builds_by_unexisting_package(self):
        res = self.app.get('/builds/', {"packages": "flash"}, status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'packages')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid packages specified: flash')

    def test_list_builds_by_release_name(self):
        res = self.app.get('/builds/', {"releases": "F17"})
        body = res.json_body
        self.assertEquals(len(body['builds']), 1)

        up = body['builds'][0]
        self.assertEquals(up['nvr'], u'bodhi-2.0-1.fc17')

    def test_list_builds_by_release_version(self):
        res = self.app.get('/builds/', {"releases": "17"})
        body = res.json_body
        self.assertEquals(len(body['builds']), 1)

        up = body['builds'][0]
        self.assertEquals(up['nvr'], u'bodhi-2.0-1.fc17')

    def test_list_builds_by_unexisting_release(self):
        res = self.app.get('/builds/', {"releases": "WinXP"}, status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'releases')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid releases specified: WinXP')
