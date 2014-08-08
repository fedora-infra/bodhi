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
    stackstate,
    Update,
    UpdateType,
    UpdateStatus,
    UpdateRequest,
)


class TestStacksService(bodhi.tests.functional.base.BaseWSGICase):

    def setUp(self):
        super(TestStacksService, self).setUp()
        session = DBSession()
        stack = Stack(name=u'GNOME')
        session.add(stack)
        session.flush()

    def test_404(self):
        self.app.get('/stacks/watwatwat', status=404)

    def test_get_single_stack_by_lower(self):
        res = self.app.get('/stacks/f22')
        self.assertEquals(res.json_body['name'], 'F22')

    #def test_get_single_stack_by_upper(self):
    #    res = self.app.get('/stacks/F22')
    #    self.assertEquals(res.json_body['name'], 'F22')

    #def test_list_stacks(self):
    #    res = self.app.get('/stacks/')
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 2)
    #    self.assertEquals(body['stacks'][0]['name'], u'F17')
    #    self.assertEquals(body['stacks'][1]['name'], u'F22')

    #def test_list_stacks_with_pagination(self):
    #    res = self.app.get('/stacks/')
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 2)

    #    res = self.app.get('/stacks/', {'rows_per_page': 1})
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 1)
    #    self.assertEquals(body['stacks'][0]['name'], 'F17')

    #    res = self.app.get('/stacks/', {'rows_per_page': 1, 'page': 2})
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 1)
    #    self.assertEquals(body['stacks'][0]['name'], 'F22')

    #def test_list_stacks_by_name(self):
    #    res = self.app.get('/stacks/', {"name": 'F22'})
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 1)
    #    self.assertEquals(body['stacks'][0]['name'], 'F22')

    #def test_list_stacks_by_name_match(self):
    #    res = self.app.get('/stacks/', {"name": '%1%'})
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 1)
    #    self.assertEquals(body['stacks'][0]['name'], 'F17')

    #def test_list_stacks_by_name_match_miss(self):
    #    res = self.app.get('/stacks/', {"name": '%wat%'})
    #    self.assertEquals(len(res.json_body['stacks']), 0)

    #def test_list_stacks_by_update_title(self):
    #    res = self.app.get('/stacks/', {"updates": 'bodhi-2.0-1.fc17'})
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 1)
    #    self.assertEquals(body['stacks'][0]['name'], 'F17')

    #def test_list_stacks_by_update_alias(self):
    #    session = DBSession()
    #    update = session.query(Update).first()
    #    update.alias = 'some_alias'
    #    session.flush()

    #    res = self.app.get('/stacks/', {"updates": 'some_alias'})
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 1)
    #    self.assertEquals(body['stacks'][0]['name'], 'F17')

    #def test_list_stacks_by_nonexistant_update(self):
    #    res = self.app.get('/stacks/', {"updates": 'carbunkle'}, status=400)
    #    self.assertEquals(res.json_body['errors'][0]['name'], 'updates')
    #    self.assertEquals(res.json_body['errors'][0]['description'],
    #                      'Invalid updates specified: carbunkle')

    #def test_list_stacks_by_package_name(self):
    #    res = self.app.get('/stacks/', {"packages": 'bodhi'})
    #    body = res.json_body
    #    self.assertEquals(len(body['stacks']), 1)
    #    self.assertEquals(body['stacks'][0]['name'], 'F17')

    #def test_list_stacks_by_nonexistant_package(self):
    #    res = self.app.get('/stacks/', {"packages": 'carbunkle'}, status=400)
    #    self.assertEquals(res.json_body['errors'][0]['name'], 'packages')
    #    self.assertEquals(res.json_body['errors'][0]['description'],
    #                      'Invalid packages specified: carbunkle')

    #def test_new_stack(self):
    #    attrs = {"name": "KDE"}
    #    res = self.app.post("/stacks/", attrs, status=200)
    #    r = DBSession().query(Stack).filter(Stack.name==attrs["name"]).one()

    #    for k, v in attrs.items():
    #        self.assertEquals(getattr(r, k), v)

    #def test_edit_stack(self):
    #    name = "GNOME"

    #    res = self.app.get('/stacks/%s' % name, status=200)
    #    r = res.json_body

    #    r["edited"] = name
    #    r["state"] = "current"

    #    res = self.app.post("/stacks/", r, status=200)

    #    r = DBSession().query(Release).filter(Release.name==name).one()
    #    self.assertEquals(r.state, stackstate.current)
