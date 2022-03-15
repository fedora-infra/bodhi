# Copyright © 2014-2019 Red Hat, Inc. and others.
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

from datetime import datetime, timedelta
from unittest import mock
import copy

from fedora_messaging import api
from fedora_messaging import testing as fml_testing
import webtest

from bodhi.messages.schemas import buildroot_override as override_schemas
from bodhi.server import main
from bodhi.server.models import (
    BuildrootOverride,
    PackageManager,
    Release,
    RpmBuild,
    RpmPackage,
    TestGatingStatus,
    Update,
    User,
)

from .. import base


class TestOverridesService(base.BasePyTestCase):
    def test_404_build_not_found(self):
        """Test a 404 due to the build for the override not existing."""
        self.app.get('/overrides/watwatwat', status=404)

    def test_404_override_not_found(self):
        """Test a 404 when the build does exist, but there is no override for it."""
        b = RpmBuild.query.first()
        BuildrootOverride.query.filter_by(build=b).delete()
        b.override = None
        self.db.commit()

        self.app.get('/overrides/{}'.format(b.nvr), status=404)

    def test_get_single_override(self):
        res = self.app.get('/overrides/bodhi-2.0-1.fc17', headers={'Accept': 'application/json'})

        override = res.json_body['override']

        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"
        assert override['submitter']['name'] == 'guest'
        assert override['notes'] == 'blah blah blah'

    def test_list_overrides(self):
        res = self.app.get('/overrides/')

        body = res.json_body
        assert len(body['overrides']) == 1

        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"
        assert override['submitter']['name'] == 'guest'
        assert override['notes'] == 'blah blah blah'

    def test_list_overrides_rss(self):
        res = self.app.get('/rss/overrides/',
                           headers=dict(accept='application/atom+xml'))
        assert 'application/rss+xml' in res.headers['Content-Type']
        assert 'blah blah blah' in res

    def test_list_expired_overrides(self):
        res = self.app.get('/overrides/', {'expired': 'true'})

        body = res.json_body
        assert len(body['overrides']) == 0

    def test_list_notexpired_overrides(self):
        res = self.app.get('/overrides/', {'expired': 'false'})

        body = res.json_body
        assert len(body['overrides']) == 1

        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"
        assert override['submitter']['name'] == 'guest'
        assert override['notes'] == 'blah blah blah'

    def test_list_overrides_by_invalid_expired(self):
        res = self.app.get('/overrides/', {"expired": "lalala"},
                           status=400)
        errors = res.json_body['errors']
        assert len(res.json_body.get('overrides', [])) == 0
        assert len(errors) == 1
        assert errors[0]['name'] == 'expired'
        assert errors[0]['description'] == \
            '"lalala" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')'

    def test_list_overrides_by_packages(self):
        res = self.app.get('/overrides/', {'packages': 'bodhi'})

        body = res.json_body
        assert len(body['overrides']) == 1

        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"
        assert override['submitter']['name'] == 'guest'
        assert override['notes'] == 'blah blah blah'

    def test_list_overrides_by_packages_without_override(self):
        self.db.add(RpmPackage(name='python'))
        self.db.flush()

        res = self.app.get('/overrides/', {'packages': 'python'})

        body = res.json_body
        assert len(body['overrides']) == 0

    def test_list_overrides_by_invalid_packages(self):
        res = self.app.get('/overrides/', {'packages': 'flash-player'},
                           status=400)

        errors = res.json_body['errors']
        assert len(res.json_body.get('overrides', [])) == 0
        assert len(errors) == 1
        assert errors[0]['name'] == 'packages'
        assert errors[0]['description'] == 'Invalid packages specified: flash-player'

    def test_list_overrides_by_releases(self):
        res = self.app.get('/overrides/', {'releases': 'F17'})

        body = res.json_body
        assert len(body['overrides']) == 1

        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"
        assert override['submitter']['name'] == 'guest'
        assert override['notes'] == 'blah blah blah'

    def test_list_overrides_by_builds(self):
        res = self.app.get('/overrides/', {'builds': 'bodhi-2.0-1.fc17'})

        body = res.json_body
        assert len(body['overrides']) == 1

        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"
        assert override['submitter']['name'] == 'guest'
        assert override['notes'] == 'blah blah blah'

    def test_list_overrides_by_releases_without_override(self):
        self.db.add(Release(name='F42', long_name='Fedora 42',
                            id_prefix='FEDORA', version='42',
                            dist_tag='f42', stable_tag='f42-updates',
                            testing_tag='f42-updates-testing',
                            candidate_tag='f42-updates-candidate',
                            pending_signing_tag='f42-updates-testing-signing',
                            pending_testing_tag='f42-updates-testing-pending',
                            pending_stable_tag='f42-updates-pending',
                            override_tag='f42-override',
                            branch='f42',
                            package_manager=PackageManager.dnf,
                            testing_repository='updates-testing'))
        self.db.flush()

        res = self.app.get('/overrides/', {'releases': 'F42'})

        body = res.json_body
        assert len(body['overrides']) == 0

    def test_list_overrides_by_invalid_releases(self):
        res = self.app.get('/overrides/', {'releases': 'F42'},
                           status=400)

        errors = res.json_body['errors']
        assert len(res.json_body.get('overrides', [])) == 0
        assert len(errors) == 1
        assert errors[0]['name'] == 'releases'
        assert errors[0]['description'] == 'Invalid releases specified: F42'

    def test_list_overrides_by_username(self):
        res = self.app.get('/overrides/', {"user": "guest"})
        body = res.json_body
        assert len(body['overrides']) == 1

        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"
        assert override['submitter']['name'] == 'guest'
        assert override['notes'] == 'blah blah blah'

    def test_list_overrides_by_multiple_usernames(self):
        release = Release.get('F17')

        package = RpmPackage(name='just-testing')
        self.db.add(package)
        build = RpmBuild(nvr='just-testing-1.0-2.fc17', package=package, release=release)
        self.db.add(build)
        another_user = User(name='aUser')
        self.db.add(another_user)

        expiration_date = datetime.utcnow() + timedelta(days=1)

        override = BuildrootOverride(build=build, submitter=another_user,
                                     notes='Crazy! 😱',
                                     expiration_date=expiration_date)
        self.db.add(override)
        self.db.flush()

        res = self.app.get('/overrides/', {"user": "guest,aUser"})
        body = res.json_body
        assert len(body['overrides']) == 2

        override_fake = body['overrides'][0]
        assert override_fake['build']['nvr'] == 'just-testing-1.0-2.fc17'
        assert override_fake['submitter']['name'] == 'aUser'
        assert override_fake['notes'] == 'Crazy! 😱'

        override_orig = body['overrides'][1]
        assert override_orig['build']['nvr'] == 'bodhi-2.0-1.fc17'
        assert override_orig['submitter']['name'] == 'guest'
        assert override_orig['notes'] == 'blah blah blah'

    def test_list_overrides_by_username_without_override(self):
        self.db.add(User(name='bochecha'))
        self.db.flush()

        res = self.app.get('/overrides/', {'user': 'bochecha'})

        body = res.json_body
        assert len(body['overrides']) == 0

    def test_list_overrides_by_nonexistent_username(self):
        res = self.app.get('/overrides/', {"user": "santa"}, status=400)

        errors = res.json_body['errors']
        assert len(res.json_body.get('overrides', [])) == 0
        assert len(errors) == 1
        assert errors[0]['name'] == 'user'
        assert errors[0]['description'] == "Invalid users specified: santa"

    def test_list_overrides_by_like(self):
        """
        Test that the overrides/?like= endpoint works as expected
        """

        # test that like works
        res = self.app.get('/overrides/', {"like": "bodh"})
        body = res.json_body
        assert len(body['overrides']) == 1
        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"

        # test a like that yields nothing
        res = self.app.get('/overrides/', {"like": "corebird"})
        body = res.json_body
        assert len(body['overrides']) == 0

    def test_list_overrides_by_search(self):
        """
        Test that the overrides/?search= endpoint works as expected
        """

        # test that search works
        res = self.app.get('/overrides/', {"search": "bodh"})
        body = res.json_body
        assert len(body['overrides']) == 1
        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"

        # test a search that is case-insensitive
        res = self.app.get('/overrides/', {"search": "Bodh"})
        assert len(body['overrides']) == 1
        override = body['overrides'][0]
        assert override['build']['nvr'] == "bodhi-2.0-1.fc17"

        # test a search that yields nothing
        res = self.app.get('/overrides/', {"search": "corebird"})
        body = res.json_body
        assert len(body['overrides']) == 0

    def test_create_override(self):
        release = Release.get('F17')

        package = RpmPackage(name='not-bodhi')
        self.db.add(package)
        build = RpmBuild(nvr='not-bodhi-2.0-2.fc17', package=package, release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': 'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideTagV1):
            res = self.app.post('/overrides/', data)

        o = res.json_body
        assert o['build_id'] == build.id
        assert o['notes'] == 'blah blah blah'
        assert o['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert o['expired_date'] is None

    def test_create_override_for_build_with_test_gating_status_failed(self):
        """
        Test that Override is not created when the test gating status is failed.
        """
        release = Release.get('F17')
        package = RpmPackage(name='not-bodhi')
        self.db.add(package)
        build = RpmBuild(nvr='not-bodhi-2.0-2.fc17', package=package, release=release)
        update = Update.query.first()
        update.builds.append(build)
        update.test_gating_status = TestGatingStatus.failed
        self.db.add(build)
        self.db.flush()
        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': 'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}

        with fml_testing.mock_sends():
            res = self.app.post('/overrides/', data, status=400)

        errors = res.json_body['errors']
        assert len(errors) == 1
        assert errors[0]['name'] == 'nvr'
        assert errors[0]['description'] == \
            "Cannot create a buildroot override if build's test gating status is failed."

    def test_create_duplicate_override(self):
        """When creating a duplicate override, old notes are appended."""
        release = Release.get('F17')
        package = RpmPackage(name='not-bodhi')
        self.db.add(package)
        build = RpmBuild(nvr='not-bodhi-2.0-2.fc17', package=package, release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': 'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideTagV1):
            res = self.app.post('/overrides/', data)

        o = res.json_body
        assert o['build_id'] == build.id
        assert o['notes'] == 'blah blah blah'
        assert o['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert o['expired_date'] is None

        # Submit it again
        data['notes'] = 'new blah blah'
        res = self.app.post('/overrides/', data)
        o = res.json_body
        new_notes = f"""new blah blah
_____________
_@guest ({datetime.utcnow().strftime('%b %d, %Y')})_
blah blah blah"""
        assert o['notes'] == new_notes

    def test_create_duplicate_override_notes_too_long(self):
        """When notes are too long, truncate the older."""
        release = Release.get('F17')
        package = RpmPackage(name='not-bodhi')
        self.db.add(package)
        build = RpmBuild(nvr='not-bodhi-2.0-2.fc17', package=package, release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': 'blah' * 500,
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideTagV1):
            res = self.app.post('/overrides/', data)

        o = res.json_body
        assert o['build_id'] == build.id
        assert o['notes'] == 'blah' * 500
        assert o['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert o['expired_date'] is None

        # Submit it again
        data['notes'] = 'new blah blah'
        res = self.app.post('/overrides/', data)
        o = res.json_body
        assert o['notes'].endswith('(...)\n___Notes truncated___')
        assert len(o['notes']) <= 2000

    def test_create_override_multiple_nvr(self):
        release = Release.get('F17')
        package = RpmPackage(name='not-bodhi')
        self.db.add(package)
        build1 = RpmBuild(nvr='not-bodhi-2.0-2.fc17', package=package, release=release)
        self.db.add(build1)
        self.db.flush()

        package = RpmPackage(name='another-not-bodhi')
        self.db.add(package)
        build2 = RpmBuild(nvr='another-not-bodhi-2.0-2.fc17', package=package, release=release)
        self.db.add(build2)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {
            'nvr': ','.join([build1.nvr, build2.nvr]),
            'notes': 'blah blah blah',
            'expiration_date': expiration_date,
            'csrf_token': self.get_csrf_token(),
        }

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideTagV1,
                                    override_schemas.BuildrootOverrideTagV1):
            res = self.app.post('/overrides/', data)

        result = res.json_body
        assert result['caveats'][0]['description'] == 'Your override submission was split into 2.'

        o1, o2 = result['overrides']
        assert o1['build_id'] == build1.id
        assert o1['notes'] == 'blah blah blah'
        assert o1['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert o1['expired_date'] is None
        assert o2['build_id'] == build2.id
        assert o2['notes'] == 'blah blah blah'
        assert o2['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert o2['expired_date'] is None

    def test_create_override_too_long(self):
        release = Release.get('F17')

        package = RpmPackage(name='not-bodhi')
        self.db.add(package)
        build = RpmBuild(nvr='not-bodhi-2.0-2.fc17', package=package, release=release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=60)

        data = {'nvr': build.nvr, 'notes': 'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}
        self.app.post('/overrides/', data, status=400)

    def test_create_override_for_newer_build(self):
        old_build = RpmBuild.get('bodhi-2.0-1.fc17')

        build = RpmBuild(nvr='bodhi-2.0-2.fc17', package=old_build.package,
                         release=old_build.release)
        self.db.add(build)
        self.db.flush()

        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': build.nvr, 'notes': 'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}
        expected_messages = (
            override_schemas.BuildrootOverrideUntagV1,
            override_schemas.BuildrootOverrideTagV1)

        with fml_testing.mock_sends(*expected_messages):
            res = self.app.post('/overrides/', data)

        o = res.json_body
        assert o['build_id'] == build.id
        assert o['notes'] == 'blah blah blah'
        assert o['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert o['expired_date'] is None

        old_build = RpmBuild.get('bodhi-2.0-1.fc17')

        assert old_build.override['expired_date'] is not None

    def test_cannot_edit_override_build(self):
        release = Release.get('F17')

        old_nvr = 'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr,
                           headers={'Accept': 'application/json'})
        o = res.json_body['override']
        expiration_date = o['expiration_date']
        old_build_id = o['build_id']

        build = RpmBuild(nvr='bodhi-2.0-2.fc17', release=release,
                         package=RpmPackage.query.filter_by(name='bodhi').one())
        self.db.add(build)
        self.db.flush()

        o.update({
            'nvr': build.nvr,
            'edited': old_nvr,
            'csrf_token': self.get_csrf_token(),
        })

        with fml_testing.mock_sends():
            res = self.app.post('/overrides/', o)

        override = res.json_body
        assert override['build_id'] == old_build_id
        assert override['notes'] == 'blah blah blah'
        assert override['expiration_date'] == expiration_date
        assert override['expired_date'] is None

    def test_edit_nonexistent_build(self):
        """
        Validate the handler for an override that exists with an edit on a build that doesn't.

        We're doing to do something weird in this test. We're going to edit an override nvr that is
        not a 404, but we're going to set the edited property to a build that does not exist. The
        service should handle this by giving us an error.
        """
        build = RpmBuild.query.first()
        expiration_date = datetime.utcnow() + timedelta(days=1)
        o = {
            'nvr': build.nvr,
            'notes': 'blah blah blah',
            'expiration_date': expiration_date,
            'edited': 'does not exist!',
            'csrf_token': self.get_csrf_token(),
        }

        res = self.app.post('/overrides/', o, status=400)

        errors = res.json_body['errors']
        assert len(errors) == 1
        assert errors[0]['name'] == 'edited'
        assert errors[0]['description'] == 'No such build'

    def test_edit_nonexistent_override(self):
        release = Release.get('F17')

        build = RpmBuild(nvr='bodhi-2.0-2.fc17', release=release,
                         package=RpmPackage.query.filter_by(name='bodhi').one())
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
        assert len(errors) == 1
        assert errors[0]['name'] == 'edited'
        assert errors[0]['description'] == 'No buildroot override for this build'

    @mock.patch('bodhi.server.services.overrides.BuildrootOverride.edit',
                mock.MagicMock(side_effect=IOError('no db for you!')))
    def test_edit_unexpected_error(self):
        """Validate that Exceptions are handled when editing overrides."""
        build = RpmBuild.query.first()
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
        assert len(errors) == 1
        assert errors[0]['name'] == 'override'
        assert errors[0]['description'] == 'Unable to save buildroot override: no db for you!'

    def test_edit_notes(self):
        old_nvr = 'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr,
                           headers={'Accept': 'application/json'})
        o = res.json_body['override']
        build_id = o['build_id']
        expiration_date = o['expiration_date']

        o.update({'nvr': old_nvr, 'notes': 'blah blah blah blah',
                  'edited': old_nvr, 'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        assert override['build_id'] == build_id
        assert override['notes'] == 'blah blah blah blah'
        assert override['expiration_date'] == expiration_date
        assert override['expired_date'] is None

    def test_edit_expiration_date(self):
        old_nvr = 'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr,
                           headers={'Accept': 'application/json'})
        o = res.json_body['override']
        expiration_date = datetime.utcnow() + timedelta(days=2)

        o.update({'nvr': o['build']['nvr'],
                  'expiration_date': expiration_date, 'edited': old_nvr,
                  'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o)

        override = res.json_body
        assert override['build'] == o['build']
        assert override['notes'] == o['notes']
        assert override['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert override['expired_date'] is None

    def test_edit_fail_on_multiple(self):
        old_nvr = 'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr,
                           headers={'Accept': 'application/json'})
        o = res.json_body['override']
        o.update({'nvr': old_nvr + ',wat', 'notes': 'blah blah blah blah',
                  'edited': old_nvr, 'csrf_token': self.get_csrf_token()})
        res = self.app.post('/overrides/', o, status=400)
        result = res.json_body
        assert result['errors'][0]['description'] == \
            'Cannot combine multiple NVRs with editing a buildroot override.'

    def test_expire_override(self):
        old_nvr = 'bodhi-2.0-1.fc17'

        res = self.app.get('/overrides/%s' % old_nvr,
                           headers={'Accept': 'application/json'})
        o = res.json_body['override']

        o.update({'nvr': o['build']['nvr'], 'expired': True,
                  'edited': old_nvr, 'csrf_token': self.get_csrf_token()})

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideUntagV1):
            res = self.app.post('/overrides/', o)

        override = res.json_body
        assert override['build'] == o['build']
        assert override['notes'] == o['notes']
        assert override['expiration_date'] == o['expiration_date']
        assert override['expired_date'] is not None

    def test_unexpire_override(self):
        # First expire a buildroot override
        old_nvr = 'bodhi-2.0-1.fc17'
        override = RpmBuild.get(old_nvr).override

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideUntagV1):
            override.expire()
            self.db.commit()

        self.db.add(override)
        self.db.flush()

        # And now push its expiration_date into the future
        res = self.app.get('/overrides/%s' % old_nvr,
                           headers={'Accept': 'application/json'})
        o = res.json_body['override']

        expiration_date = datetime.now() + timedelta(days=1)
        expiration_date = expiration_date.strftime("%Y-%m-%d %H:%M:%S")

        o.update({'nvr': o['build']['nvr'],
                  'edited': old_nvr, 'expiration_date': expiration_date,
                  'csrf_token': self.get_csrf_token()})

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideTagV1):
            res = self.app.post('/overrides/', o)

        override = res.json_body
        assert override['build'] == o['build']
        assert override['notes'] == o['notes']
        assert override['expiration_date'] == o['expiration_date']
        assert override['expired_date'] is None

    def test_create_override_with_missing_pkg(self):
        nvr = 'not-bodhi-2.0-2.fc17'
        expiration_date = datetime.utcnow() + timedelta(days=1)

        data = {'nvr': nvr, 'notes': 'blah blah blah',
                'expiration_date': expiration_date,
                'csrf_token': self.get_csrf_token()}

        with fml_testing.mock_sends(override_schemas.BuildrootOverrideTagV1):
            res = self.app.post('/overrides/', data,
                                headers={'Accept': 'application/json'})

        o = res.json_body
        assert o['nvr'] == nvr
        assert o['notes'] == 'blah blah blah'
        assert o['expiration_date'] == expiration_date.strftime("%Y-%m-%d %H:%M:%S")
        assert o['expired_date'] is None


class TestOverridesWebViews(base.BasePyTestCase):
    def test_override_view_not_loggedin(self):
        """
        Test a non logged in User can't see the edit overrides form
        """
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        with mock.patch('bodhi.server.Session.remove'):
            app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))

        resp = app.get('/overrides/bodhi-2.0-1.fc17',
                       status=200, headers={'Accept': 'text/html'})
        assert '<h3>New Buildroot Override Form Requires JavaScript</h3>' not in resp
        assert '<code>bodhi-2.0-1.fc17</code>' in resp

    def test_override_view_loggedin(self):
        """
        Test a logged in User can see the edit overrides form, and the correct
        override is shown
        """
        resp = self.app.get('/overrides/bodhi-2.0-1.fc17',
                            status=200, headers={'Accept': 'text/html'})
        assert '<h3>New Buildroot Override Form Requires JavaScript</h3>' in resp
        assert '<code>bodhi-2.0-1.fc17</code>' in resp

    def test_override_new_not_loggedin(self):
        """
        Test a non logged in User is forbidden from viewing the new overrides page
        """
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))
        resp = app.get('/overrides/new',
                       status=403, headers={'Accept': 'text/html'})
        assert '<h1>403 <small>Forbidden</small></h1>' in resp
        assert '<p class="lead">You must be logged in.</p>' in resp

    def test_override_new_loggedin(self):
        """
        Test a logged in User can see the new overrides form
        """
        resp = self.app.get('/overrides/new',
                            status=200, headers={'Accept': 'text/html'})
        assert 'Create New Override' in resp

    def test_overrides_list(self):
        """
        Test that the overrides list page shows, and contains the one overrides
        in the test data.
        """
        resp = self.app.get('/overrides/',
                            status=200, headers={'Accept': 'text/html'})
        assert '<h3 class="font-weight-bold m-0 d-flex align-items-center">Overrides' in resp
        assert '<a href="http://localhost/overrides/bodhi-2.0-1.fc17">' in resp

    @mock.patch('bodhi.server.util.arrow.get')
    def test_override_expired_date(self, get):
        """
        Test that a User can see the expired date of the override
        """
        get.return_value.humanize.return_value = '82 seconds bro ago'
        expiration_date = datetime.utcnow() + timedelta(days=1)
        data = {'nvr': 'bodhi-2.0-1.fc17', 'notes': 'blah blah blah',
                'expiration_date': expiration_date,
                'edited': 'bodhi-2.0-1.fc17', 'expired': True,
                'csrf_token': self.get_csrf_token()}

        with fml_testing.mock_sends(api.Message):
            self.app.post('/overrides/', data)
        resp = self.app.get('/overrides/bodhi-2.0-1.fc17',
                            status=200, headers={'Accept': 'text/html'})

        assert ("<span class='col-xs-auto pr-2 ml-auto text-danger'><small>"
                "expired <strong>82 seconds bro ago</strong></small></span>") in resp
        assert abs((get.mock_calls[0][1][0] - expiration_date).seconds) < 64
