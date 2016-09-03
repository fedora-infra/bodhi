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

import mock

import bodhi.tests.server.functional.base

from bodhi.server.models import (
    Group,
    Package,
    User,
    Stack,
)


mock_valid_requirements = {
    'target': 'bodhi.server.validators._get_valid_requirements',
    'return_value': ['rpmlint', 'upgradepath'],
}


class TestStacksService(bodhi.tests.server.functional.base.BaseWSGICase):

    def setUp(self):
        super(TestStacksService, self).setUp()
        package = Package(name=u'gnome-shell')
        self.db.add(package)
        self.db.flush()
        self.stack = stack = Stack(name=u'GNOME', packages=[package])
        self.db.add(stack)
        self.db.flush()

    def test_404(self):
        self.app.get('/stacks/watwatwat', status=404)

    def test_get_single_stack(self):
        res = self.app.get('/stacks/GNOME')
        self.assertEquals(res.json_body['stack']['name'], u'GNOME')
        self.assertEquals(res.json_body['stack']['packages'][0]['name'], u'gnome-shell')

    def test_list_stacks(self):
        res = self.app.get('/stacks/')
        body = res.json_body
        self.assertEquals(len(body['stacks']), 1)
        self.assertEquals(body['stacks'][0]['name'], u'GNOME')
        self.assertEquals(body['stacks'][0]['packages'][0]['name'], u'gnome-shell')

    def test_list_stacks_with_pagination(self):
        # Create a second stack
        pkg1 = Package(name=u'firefox')
        pkg2 = Package(name=u'xulrunner')
        self.db.add(pkg1)
        self.db.add(pkg2)
        self.db.flush()
        Stack(name=u'Firefox', packages=[pkg1, pkg2])
        self.db.flush()

        res = self.app.get('/stacks/')
        body = res.json_body
        self.assertEquals(len(body['stacks']), 2)

        res = self.app.get('/stacks/', {'rows_per_page': 1})
        body = res.json_body
        self.assertEquals(len(body['stacks']), 1)
        self.assertEquals(body['stacks'][0]['name'], u'GNOME')

        res = self.app.get('/stacks/', {'rows_per_page': 1, 'page': 2})
        body = res.json_body
        self.assertEquals(len(body['stacks']), 1)
        self.assertEquals(body['stacks'][0]['name'], 'Firefox')
        self.assertEquals(body['stacks'][0]['packages'][0]['name'], 'firefox')

    def test_list_stacks_by_name(self):
        res = self.app.get('/stacks/', {'name': 'GNOME'})
        body = res.json_body
        self.assertEquals(len(body['stacks']), 1)
        self.assertEquals(body['stacks'][0]['name'], 'GNOME')

    def test_list_stacks_by_name_mismatch(self):
        res = self.app.get('/stacks/', {'like': '%KDE%'})
        body = res.json_body
        self.assertEquals(len(body['stacks']), 0)

    def test_list_stacks_by_name_match(self):
        res = self.app.get('/stacks/', {'like': '%GN%'})
        body = res.json_body
        self.assertEquals(len(body['stacks']), 1)
        self.assertEquals(body['stacks'][0]['name'], 'GNOME')

    def test_list_stacks_by_package_name(self):
        res = self.app.get('/stacks/', {"packages": 'gnome-shell'})
        body = res.json_body
        self.assertEquals(len(body['stacks']), 1)
        self.assertEquals(body['stacks'][0]['name'], 'GNOME')

    def test_list_stacks_by_nonexistant_package(self):
        res = self.app.get('/stacks/', {"packages": 'carbunkle'}, status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'packages')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid packages specified: carbunkle')

    @mock.patch(**mock_valid_requirements)
    def test_new_stack(self, *args):
        attrs = {'name': 'KDE', 'packages': 'kde-filesystem kdegames',
                 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=200)
        body = res.json_body['stack']
        self.assertEquals(body['name'], 'KDE')
        r = self.db.query(Stack).filter(Stack.name==attrs["name"]).one()
        self.assertEquals(r.name, 'KDE')
        self.assertEquals(len(r.packages), 2)
        self.assertEquals(r.packages[0].name, 'kde-filesystem')
        self.assertEquals(r.requirements, 'rpmlint')

    @mock.patch(**mock_valid_requirements)
    def test_new_stack_invalid_name(self, *args):
        attrs = {"name": "", 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=400)
        self.assertEquals(res.json_body['status'], 'error')

    @mock.patch(**mock_valid_requirements)
    def test_new_stack_invalid_requirement(self, *args):
        attrs = {"name": "Hackey", "packages": "nethack",
                 "requirements": "silly-dilly",
                 "csrf_token": self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=400)
        self.assertEquals(res.json_body['status'], 'error')
        c = self.db.query(Stack).filter(Stack.name==attrs["name"]).count()
        self.assertEquals(c, 0)

    @mock.patch(**mock_valid_requirements)
    def test_new_stack_valid_requirement(self, *args):
        attrs = {"name": "Hackey", "packages": "nethack",
                 "requirements": "rpmlint",
                 "csrf_token": self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs)#, status=200)
        body = res.json_body['stack']
        self.assertEquals(body['name'], 'Hackey')
        r = self.db.query(Stack).filter(Stack.name==attrs["name"]).one()
        self.assertEquals(r.name, 'Hackey')
        self.assertEquals(len(r.packages), 1)
        self.assertEquals(r.requirements, attrs['requirements'])

    @mock.patch(**mock_valid_requirements)
    def test_edit_stack(self, *args):
        attrs = {'name': 'GNOME', 'packages': 'gnome-music gnome-shell',
                 'description': 'foo', 'requirements': 'upgradepath',
                 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=200)
        body = res.json_body['stack']
        self.assertEquals(body['name'], 'GNOME')
        self.assertEquals(len(body['packages']), 2)
        self.assertEquals(body['packages'][-1]['name'], 'gnome-music')
        self.assertEquals(body['description'], 'foo')
        self.assertEquals(body['requirements'], 'upgradepath')

        # Adding gnome-music to the stack should change its requirements, too.
        package = self.db.query(Package)\
            .filter(Package.name==u'gnome-music').one()
        self.assertEquals(package.requirements, attrs['requirements'])

        # But not gnome-shell, since it was already in the stack.
        package = self.db.query(Package)\
            .filter(Package.name==u'gnome-shell').one()
        self.assertEquals(package.requirements, None)

    def test_delete_stack(self):
        res = self.app.delete("/stacks/GNOME")
        self.assertEquals(res.json_body['status'], 'success')
        self.assertEquals(self.db.query(Stack).count(), 0)

    @mock.patch(**mock_valid_requirements)
    def test_edit_stack_remove_package(self, *args):
        attrs = {'name': 'GNOME', 'packages': 'gnome-music',
                 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=200)
        body = res.json_body['stack']
        self.assertEquals(body['name'], 'GNOME')
        self.assertEquals(len(body['packages']), 1)
        self.assertEquals(body['packages'][0]['name'], 'gnome-music')

    @mock.patch(**mock_valid_requirements)
    def test_edit_stack_with_no_group_privs(self, *args):
        self.stack.users = []
        group = Group(name=u'gnome-team')
        self.db.add(group)
        self.db.flush()
        self.stack.groups.append(group)
        self.db.flush()
        attrs = {'name': 'GNOME', 'packages': 'gnome-music gnome-shell',
                 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=403)
        body = res.json_body
        self.assertEquals(body['status'], 'error')
        self.assertEquals(body['errors'][0]['description'],
                'guest does not have privileges to modify the GNOME stack')

    @mock.patch(**mock_valid_requirements)
    def test_edit_stack_with_no_user_privs(self, *args):
        user = User(name=u'bob')
        self.db.add(user)
        self.db.flush()
        self.stack.users.append(user)
        self.db.flush()
        attrs = {'name': 'GNOME', 'packages': 'gnome-music gnome-shell',
                 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=403)
        body = res.json_body
        self.assertEquals(body['status'], 'error')
        self.assertEquals(body['errors'][0]['description'],
                'guest does not have privileges to modify the GNOME stack')

    @mock.patch(**mock_valid_requirements)
    def test_edit_stack_with_user_privs(self, *args):
        user = self.db.query(User).filter_by(name=u'guest').one()
        self.stack.users.append(user)
        self.db.flush()
        attrs = {'name': 'GNOME', 'packages': 'gnome-music gnome-shell',
                 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=200)
        body = res.json_body['stack']
        self.assertEquals(body['name'], 'GNOME')
        self.assertEquals(len(body['packages']), 2)
        self.assertEquals(body['packages'][-1]['name'], 'gnome-music')

    @mock.patch(**mock_valid_requirements)
    def test_edit_stack_with_group_privs(self, *args):
        self.stack.users = []
        user = self.db.query(User).filter_by(name=u'guest').one()
        group = Group(name=u'gnome-team')
        self.db.add(group)
        self.db.flush()
        self.stack.groups.append(group)
        user.groups.append(group)
        self.db.flush()
        attrs = {'name': 'GNOME', 'packages': 'gnome-music gnome-shell',
                 'csrf_token': self.get_csrf_token()}
        res = self.app.post("/stacks/", attrs, status=200)
        body = res.json_body['stack']
        self.assertEquals(body['name'], 'GNOME')
        self.assertEquals(len(body['packages']), 2)
        self.assertEquals(body['packages'][-1]['name'], 'gnome-music')

    def test_new_stack_form(self):
        res = self.app.get('/stacks/new', status=200)
        self.assertIn('New Stack', res)
