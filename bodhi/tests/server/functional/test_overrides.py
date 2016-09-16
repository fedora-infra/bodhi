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

import bodhi.tests.server.functional.base
from bodhi.server.models import (Build, Package, Release, User)


class TestOverridesService(bodhi.tests.server.functional.base.BaseWSGICase):
    def test_404(self):
        self.app.get('/overrides/watwatwat', status=404)

    def test_get_single_override(self):
        res = self.app.get('/overrides/bodhi-2.0-1.fc17')

        override = res.json_body['override']

        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

        # check to catch performance regressions
        #self.assertEquals(len(self.sql_statements), 3)

    def test_list_overrides(self):
        res = self.app.get('/overrides/')

        body = res.json_body
        self.assertEquals(len(body['overrides']), 1)

        override = body['overrides'][0]
        self.assertEquals(override['build']['nvr'], "bodhi-2.0-1.fc17")
        self.assertEquals(override['submitter']['name'], 'guest')
        self.assertEquals(override['notes'], 'blah blah blah')

    def test_list_overrides_rss(self):
        res = self.app.get('/rss/overrides/',
                           headers=dict(accept='application/atom+xml'))
        self.assertIn('application/rss+xml', res.headers['Content-Type'])
        self.assertIn('blah blah blah', res)

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
        self.db.add(Package(name=u'python'))
        self.db.flush()

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
        self.db.add(Release(name=u'F42', long_name=u'Fedora 42',
                            id_prefix=u'FEDORA', version=u'42',
                            dist_tag=u'f42', stable_tag=u'f42-updates',
                            testing_tag=u'f42-updates-testing',
                            candidate_tag=u'f42-updates-candidate',
                            pending_signing_tag=u'f42-updates-testing-signing',
                            pending_testing_tag=u'f42-updates-testing-pending',
                            pending_stable_tag=u'f42-updates-pending',
                            override_tag=u'f42-override',
                            branch=u'f42'))
        self.db.flush()

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
        self.db.add(User(name=u'bochecha'))
        self.db.flush()

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

    @mock.patch('bodhi.server.notifications.publish')
    def test_create_override(self, publish):
        release = Release.get(u'F17', self.db)

        package = Package(name=u'not-bodhi')
        self.db.add(package)
        build = Build(nvr=u'not-bodhi-2.0-2.fc17', package=package,
                      release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': u'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}
        res = self.app.post('/overrides/', data)

        publish.assert_called_once_with(
            topic='buildroot_override.tag', msg=mock.ANY)
        self.assertEquals(len(publish.call_args_list), 1)

        o = res.json_body
        self.assertEquals(o['build_id'], build.id)
        self.assertEquals(o['notes'], 'blah blah blah')
        self.assertEquals(o['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(o['expired_date'], None)

    @mock.patch('bodhi.server.notifications.publish')
    def test_create_duplicate_override(self, publish):
        release = Release.get(u'F17', self.db)
        package = Package(name=u'not-bodhi')
        self.db.add(package)
        build = Build(nvr=u'not-bodhi-2.0-2.fc17', package=package,
                      release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': u'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}
        res = self.app.post('/overrides/', data)

        publish.assert_called_once_with(
            topic='buildroot_override.tag', msg=mock.ANY)
        self.assertEquals(len(publish.call_args_list), 1)

        o = res.json_body
        self.assertEquals(o['build_id'], build.id)
        self.assertEquals(o['notes'], 'blah blah blah')
        self.assertEquals(o['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(o['expired_date'], None)

        # Submit it again
        res = self.app.post('/overrides/', data, status=400)
        self.assertEquals(res.json_body['errors'][0]['description'],
                'Buildroot override for %s already exists' % build.nvr)

    @mock.patch('bodhi.server.notifications.publish')
    def test_create_override_multiple_nvr(self, publish):
        release = Release.get(u'F17', self.db)
        package = Package(name=u'not-bodhi')
        self.db.add(package)
        build1 = Build(nvr=u'not-bodhi-2.0-2.fc17', package=package,
                      release=release)
        self.db.add(build1)
        self.db.flush()

        package = Package(name=u'another-not-bodhi')
        self.db.add(package)
        build2 = Build(nvr=u'another-not-bodhi-2.0-2.fc17', package=package,
                      release=release)
        self.db.add(build2)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {
            'nvr': ','.join([build1.nvr, build2.nvr]),
            'notes': u'blah blah blah',
            'expiration_date': expiration_date,
            'csrf_token': self.get_csrf_token(),
        }
        res = self.app.post('/overrides/', data)

        self.assertEquals(len(publish.call_args_list), 2)

        result = res.json_body
        self.assertEquals(result['caveats'][0]['description'],
                          'Your override submission was split into 2.')

        o1, o2 = result['overrides']
        self.assertEquals(o1['build_id'], build1.id)
        self.assertEquals(o1['notes'], 'blah blah blah')
        self.assertEquals(o1['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(o1['expired_date'], None)
        self.assertEquals(o2['build_id'], build2.id)
        self.assertEquals(o2['notes'], 'blah blah blah')
        self.assertEquals(o2['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(o2['expired_date'], None)

    @mock.patch('bodhi.server.notifications.publish')
    def test_create_override_too_long(self, publish):
        release = Release.get(u'F17', self.db)

        package = Package(name=u'not-bodhi')
        self.db.add(package)
        build = Build(nvr=u'not-bodhi-2.0-2.fc17', package=package,
                      release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=60)

        data = {'nvr': build.nvr, 'notes': u'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}
        self.app.post('/overrides/', data, status=400)

    @mock.patch('bodhi.server.notifications.publish')
    def test_create_override_for_newer_build(self, publish):
        old_build = Build.get(u'bodhi-2.0-1.fc17', self.db)

        build = Build(nvr=u'bodhi-2.0-2.fc17', package=old_build.package,
                      release=old_build.release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': u'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}
        res = self.app.post('/overrides/', data)

        publish.assert_any_call(topic='buildroot_override.tag', msg=mock.ANY)
        publish.assert_any_call(
            topic='buildroot_override.untag', msg=mock.ANY)

        o = res.json_body
        self.assertEquals(o['build_id'], build.id)
        self.assertEquals(o['notes'], 'blah blah blah')
        self.assertEquals(o['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(o['expired_date'], None)

        old_build = Build.get(u'bodhi-2.0-1.fc17', self.db)

        self.assertNotEquals(old_build.override['expired_date'], None)

    @mock.patch('bodhi.server.notifications.publish')
    def test_cannot_edit_override_build(self, publish):
        release = Release.get(u'F17', self.db)

        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body['override']
        expiration_date = o['expiration_date']
        old_build_id = o['build_id']

        build = Build(nvr=u'bodhi-2.0-2.fc17', release=release)
        self.db.add(build)
        self.db.flush()

        o.update({
            'nvr': build.nvr,
            'edited': old_nvr,
            'csrf_token': self.get_csrf_token(),
        })
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build_id'], old_build_id)
        self.assertEquals(override['notes'], 'blah blah blah')
        self.assertEquals(override['expiration_date'], expiration_date)
        self.assertEquals(override['expired_date'], None)
        self.assertEquals(len(publish.call_args_list), 0)

    def test_edit_unexisting_override(self):
        release = Release.get(u'F17', self.db)

        build = Build(nvr=u'bodhi-2.0-2.fc17', release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        o = {
            'nvr': build.nvr,
            'notes': 'blah blah blah',
            'expiration_date': expiration_date,
            'edited': build.nvr,
            'csrf_token': self.get_csrf_token(),
        }
        res = self.app.post('/overrides/', o, status=400)

        errors = res.json_body['errors']
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0]['name'], 'edited')
        self.assertEquals(errors[0]['description'],
                          'No buildroot override for this build')

    def test_edit_notes(self):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body['override']
        build_id = o['build_id']
        expiration_date = o['expiration_date']

        o.update({'nvr': old_nvr, 'notes': 'blah blah blah blah',
                  'edited': old_nvr, 'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build_id'], build_id)
        self.assertEquals(override['notes'], 'blah blah blah blah')
        self.assertEquals(override['expiration_date'], expiration_date)
        self.assertEquals(override['expired_date'], None)

    def test_edit_expiration_date(self):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body['override']
        expiration_date = datetime.utcnow() + timedelta(days=2)

        o.update({'nvr': o['build']['nvr'],
                  'expiration_date': expiration_date, 'edited': old_nvr,
                  'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build'], o['build'])
        self.assertEquals(override['notes'], o['notes'])
        self.assertEquals(override['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(override['expired_date'], None)

    def test_edit_fail_on_multiple(self):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body['override']
        o.update({'nvr': old_nvr + ',wat', 'notes': 'blah blah blah blah',
                  'edited': old_nvr, 'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o, status=400)
        result = res.json_body
        self.assertEquals(
            result['errors'][0]['description'],
            'Cannot combine multiple NVRs with editing a buildroot override.',
        )

    @mock.patch('bodhi.server.notifications.publish')
    def test_expire_override(self, publish):
        old_nvr = u'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body['override']

        o.update({'nvr': o['build']['nvr'], 'expired': True,
                  'edited': old_nvr, 'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build'], o['build'])
        self.assertEquals(override['notes'], o['notes'])
        self.assertEquals(override['expiration_date'], o['expiration_date'])
        self.assertNotEquals(override['expired_date'], None)
        publish.assert_called_once_with(
            topic='buildroot_override.untag', msg=mock.ANY)

    @mock.patch('bodhi.server.notifications.publish')
    def test_unexpire_override(self, publish):
        # First expire a buildroot override
        old_nvr = u'bodhi-2.0-1.fc17'
        override = Build.get(old_nvr, self.db).override
        override.expire()
        self.db.add(override)
        self.db.flush()

        publish.assert_called_once_with(
            topic='buildroot_override.untag', msg=mock.ANY)
        publish.reset_mock()

        # And now push its expiration_date into the future
        res = self.app.get('/overrides/%s' % old_nvr)
        o = res.json_body['override']

        expiration_date = datetime.now() + timedelta(days=1)
        expiration_date = expiration_date.strftime("%Y-%m-%d %H:%M:%S")

        o.update({'nvr': o['build']['nvr'],
                  'edited': old_nvr, 'expiration_date': expiration_date,
                  'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        self.assertEquals(override['build'], o['build'])
        self.assertEquals(override['notes'], o['notes'])
        self.assertEquals(override['expiration_date'], o['expiration_date'])
        self.assertEquals(override['expired_date'], None)
        publish.assert_called_once_with(
            topic='buildroot_override.tag', msg=mock.ANY)

    @mock.patch('bodhi.server.notifications.publish')
    def test_create_override_with_missing_pkg(self, publish):
        nvr = u'not-bodhi-2.0-2.fc17'
        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': nvr, 'notes': u'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}
        res = self.app.post('/overrides/', data)

        publish.assert_called_once_with(
            topic='buildroot_override.tag', msg=mock.ANY)
        self.assertEquals(len(publish.call_args_list), 1)

        o = res.json_body
        self.assertEquals(o['nvr'], nvr)
        self.assertEquals(o['notes'], 'blah blah blah')
        self.assertEquals(o['expiration_date'],
                          expiration_date.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(o['expired_date'], None)
