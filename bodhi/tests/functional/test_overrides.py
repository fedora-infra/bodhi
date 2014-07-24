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

import mock
import colander

import bodhi.tests.functional.base
from bodhi.models import (DBSession, Build, BuildrootOverride, Package,
                          Release, User)


class TestOverridesService(bodhi.tests.functional.base.BaseWSGICase):
    def test_404(self):
        self.app.get('/overrides/watwatwat', status=404)

    def test_get_single_override(self):
        res = self.app.get('/overrides/bodhi-2.0-1.fc17')

        override = res.json_body

        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

        # check to catch performance regressions
        self.assertEquals(len(self.sql_statements), 3)

    def test_list_overrides(self):
        res = self.app.get('/overrides/')

        body = res.json_body
        self.assertEquals(len(body['overrides']), 1)

        override = body['overrides'][0]
        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

    def test_list_expired_overrides(self):
        res = self.app.get('/overrides/', {'expired': 'true'})

        body = res.json_body
        self.assertEquals(len(body['overrides']), 0)

    def test_list_notexpired_overrides(self):
        res = self.app.get('/overrides/', {'expired': 'false'})

        body = res.json_body
        self.assertEquals(len(body['overrides']), 1)

        override = body['overrides'][0]
        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

    def test_list_overrides_by_invalid_expired(self):
        res = self.app.get('/overrides/', {"expired": "lalala"},
                           status=400)
        errors = res.json_body['errors']
        self.assertEquals(len(res.json_body.get('overrides', [])), 0)
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0]['name'], 'expired')
        self.assertEquals(errors[0]['description'],
                          '"lalala" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_overrides_by_packages(self):
        res = self.app.get('/overrides/', {'packages': 'bodhi'})

        body = res.json_body
        self.assertEquals(len(body['overrides']), 1)

        override = body['overrides'][0]
        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

    def test_list_overrides_by_packages_without_override(self):
        session = DBSession()
        session.add(Package(name=u'python'))
        session.flush()

        res = self.app.get('/overrides/', {'packages': 'python'})

        body = res.json_body
        self.assertEquals(len(body['overrides']), 0)

    def test_list_overrides_by_invalid_packages(self):
        res = self.app.get('/overrides/', {'packages': 'flash-player'},
                           status=400)

        errors = res.json_body['errors']
        self.assertEquals(len(res.json_body.get('overrides', [])), 0)
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0]['name'], 'packages')
        self.assertEquals(errors[0]['description'],
                          'Invalid packages specified: flash-player')

    def test_list_overrides_by_releases(self):
        res = self.app.get('/overrides/', {'releases': 'F17'})

        body = res.json_body
        self.assertEquals(len(body['overrides']), 1)

        override = body['overrides'][0]
        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

    def test_list_overrides_by_releases_without_override(self):
        session = DBSession()
        session.add(Release(name=u'F42', long_name=u'Fedora 42',
                            id_prefix=u'FEDORA', version=u'42',
                            dist_tag=u'f42', stable_tag=u'f42-updates',
                            testing_tag=u'f42-updates-testing',
                            candidate_tag=u'f42-updates-candidate',
                            pending_testing_tag=u'f42-updates-testing-pending',
                            pending_stable_tag=u'f42-updates-pending',
                            override_tag=u'f42-override'))
        session.flush()

        res = self.app.get('/overrides/', {'releases': 'F42'})

        body = res.json_body
        self.assertEquals(len(body['overrides']), 0)

    def test_list_overrides_by_invalid_releases(self):
        res = self.app.get('/overrides/', {'releases': 'F42'},
                           status=400)

        errors = res.json_body['errors']
        self.assertEquals(len(res.json_body.get('overrides', [])), 0)
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0]['name'], 'releases')
        self.assertEquals(errors[0]['description'],
                          'Invalid releases specified: F42')

    def test_list_overrides_by_username(self):
        res = self.app.get('/overrides/', {"user": "guest"})
        body = res.json_body
        self.assertEquals(len(body['overrides']), 1)

        override = body['overrides'][0]
        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

    def test_list_overrides_by_username_without_override(self):
        session = DBSession()
        session.add(User(name=u'bochecha'))
        session.flush()

        res = self.app.get('/overrides/', {'user': 'bochecha'})

        body = res.json_body
        self.assertEquals(len(body['overrides']), 0)

    def test_list_overrides_by_unexisting_username(self):
        res = self.app.get('/overrides/', {"user": "santa"}, status=400)

        errors = res.json_body['errors']
        self.assertEquals(len(res.json_body.get('overrides', [])), 0)
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0]['name'], 'user')
        self.assertEquals(errors[0]['description'],
                          "Invalid user specified: santa")

    @mock.patch('bodhi.notifications.publish')
    def test_create_override(self, publish):
        session = DBSession()

        release = Release.get(u'F17', session)

        build = Build(nvr=u'bodhi-2.0-2.fc17', release=release)
        session.add(build)
        session.flush()

        expiration_date = datetime.now() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': u'blah blah blah',
                'expiration_date': expiration_date}
        res = self.app.post('/overrides/', data)
        publish.assert_called_once_with(
            topic='buildroot_override.tag', msg=mock.ANY)

        o = res.json_body
        self.assertEquals(o['build_id'], build.id)
        self.assertEquals(o['notes'], 'blah blah blah')
        self.assertEquals(o['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(o['expired_date'], None)

    @mock.patch('bodhi.notifications.publish')
    def test_cannot_edit_override_build(self, publish):
        session = DBSession()

        release = Release.get(u'F17', session)

        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body
        expiration_date = o['expiration_date']
        old_build_id = o['build_id']

        build = Build(nvr=u'bodhi-2.0-2.fc17', release=release)
        session.add(build)
        session.flush()

        o.update({'nvr': build.nvr, 'edited': old_nvr})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build_id'], old_build_id)
        self.assertEquals(override['notes'], 'blah blah blah')
        self.assertEquals(override['expiration_date'], expiration_date)
        self.assertEquals(override['expired_date'], None)
        self.assertEquals(len(publish.call_args_list), 0)

    def test_edit_override_build_does_not_exist(self):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body
        expiration_date = o['expiration_date']

        o.update({'nvr': u'bodhi-2.0-2.fc17', 'edited': old_nvr})
        res = self.app.post('/overrides/', o, status=400)

        errors = res.json_body['errors']
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0]['name'], 'nvr')
        self.assertEquals(errors[0]['description'], 'No such build')

    def test_edit_unexisting_override(self):
        session = DBSession()
        build = Build(nvr=u'bodhi-2.0-2.fc17')
        session.add(build)
        session.flush()

        expiration_date = datetime.now() + timedelta(days=1)

        o = {'nvr': build.nvr, 'notes': 'blah blah blah',
             'expiration_date': expiration_date, 'edited': build.nvr}
        res = self.app.post('/overrides/', o, status=400)

        errors = res.json_body['errors']
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0]['name'], 'edited')
        self.assertEquals(errors[0]['description'],
                          'No buildroot override for this build')

    def test_edit_notes(self):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body
        build_id = o['build_id']
        expiration_date = o['expiration_date']

        o.update({'nvr': old_nvr, 'notes': 'blah blah blah blah',
                  'edited': old_nvr})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build_id'], build_id)
        self.assertEquals(override['notes'], 'blah blah blah blah')
        self.assertEquals(override['expiration_date'], expiration_date)
        self.assertEquals(override['expired_date'], None)

    def test_edit_expiration_date(self):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body
        expiration_date = datetime.utcnow() + timedelta(days=2)

        o.update({'nvr': o['build']['nvr'],
                  'expiration_date': expiration_date, 'edited': old_nvr})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build'], o['build'])
        self.assertEquals(override['notes'], o['notes'])
        self.assertEquals(override['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(override['expired_date'], None)


    @mock.patch('bodhi.notifications.publish')
    def test_expire_override(self, publish):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body

        o.update({'nvr': o['build']['nvr'], 'expired': True,
                  'edited': old_nvr})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build'], o['build'])
        self.assertEquals(override['notes'], o['notes'])
        self.assertEquals(override['expiration_date'], o['expiration_date'])
        self.assertNotEquals(override['expired_date'], None)
        publish.assert_called_once_with(
            topic='buildroot_override.untag', msg=mock.ANY)
