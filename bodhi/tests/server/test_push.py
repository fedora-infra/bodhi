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
"""This test suite contains tests on the bodhi.server.push module."""

from datetime import datetime

import click

from bodhi.server import push
from bodhi.server.models import models
from bodhi.tests.server import base


class TestFilterReleases(base.BaseTestCase):
    """This test class contains tests for the _filter_releases() function."""

    def setUp(self):
        """
        Set up an archived release with an Update so we can test the filtering.
        """
        super(TestFilterReleases, self).setUp()

        self.user = self.db.query(models.User).all()[0]

        archived_release = models.Release(
            name=u'F22', long_name=u'Fedora 22',
            id_prefix=u'FEDORA', version=u'22',
            dist_tag=u'f22', stable_tag=u'f22-updates',
            testing_tag=u'f22-updates-testing',
            candidate_tag=u'f22-updates-candidate',
            pending_signing_tag=u'f22-updates-testing-signing',
            pending_testing_tag=u'f22-updates-testing-pending',
            pending_stable_tag=u'f22-updates-pending',
            override_tag=u'f22-override',
            branch=u'f22', state=models.ReleaseState.archived)
        self.db.add(archived_release)

        # Let's add an obscure package called bodhi to the release.
        pkg = self.db.query(models.Package).filter_by(name=u'bodhi').one()
        build = models.Build(nvr=u'bodhi-2.3.2-1.fc22', release=archived_release, package=pkg)
        self.db.add(build)

        # And an Update with the Build.
        self.archived_release_update = models.Update(
            title=u'bodhi-2.3.2-1.fc22', builds=[build], user=self.user,
            request=models.UpdateRequest.stable, notes=u'Useful details!', release=archived_release,
            date_submitted=datetime(2016, 10, 28), requirements=u'', stable_karma=3,
            unstable_karma=-3, type=models.UpdateType.bugfix)
        self.db.add(self.archived_release_update)

    def test_defaults_to_filtering_correct_releases(self):
        """
        Ensure that _filter_releases() filters out archived and disabled releases by default.
        """
        # To make sure the filter is skipping and including the right stuff, let's add a disabled
        # release and a pending release. Builds from the disabled one should be exlcuded and the
        # pending one should be included.
        disabled_release = models.Release(
            name=u'F21', long_name=u'Fedora 21',
            id_prefix=u'FEDORA', version=u'21',
            dist_tag=u'f21', stable_tag=u'f21-updates',
            testing_tag=u'f21-updates-testing',
            candidate_tag=u'f21-updates-candidate',
            pending_signing_tag=u'f21-updates-testing-signing',
            pending_testing_tag=u'f21-updates-testing-pending',
            pending_stable_tag=u'f21-updates-pending',
            override_tag=u'f21-override',
            branch=u'f21', state=models.ReleaseState.disabled)
        pending_release = models.Release(
            name=u'F25', long_name=u'Fedora 25',
            id_prefix=u'FEDORA', version=u'25',
            dist_tag=u'f25', stable_tag=u'f25-updates',
            testing_tag=u'f25-updates-testing',
            candidate_tag=u'f25-updates-candidate',
            pending_signing_tag=u'f25-updates-testing-signing',
            pending_testing_tag=u'f25-updates-testing-pending',
            pending_stable_tag=u'f25-updates-pending',
            override_tag=u'f25-override',
            branch=u'f25', state=models.ReleaseState.pending)
        self.db.add(disabled_release)
        self.db.add(pending_release)
        # Let's add the bodhi package to both releases.
        pkg = self.db.query(models.Package).filter_by(name=u'bodhi').one()
        disabled_build = models.Build(nvr=u'bodhi-2.3.2-1.fc21', release=disabled_release,
                                      package=pkg)
        pending_build = models.Build(nvr=u'bodhi-2.3.2-1.fc25', release=pending_release,
                                     package=pkg)
        self.db.add(disabled_build)
        self.db.add(pending_build)
        # Now let's create updates for both packages.
        disabled_release_update = models.Update(
            title=u'bodhi-2.3.2-1.fc21', builds=[disabled_build], user=self.user,
            request=models.UpdateRequest.stable, notes=u'Useful details!', release=disabled_release,
            date_submitted=datetime(2016, 10, 28), requirements=u'', stable_karma=3,
            unstable_karma=-3, type=models.UpdateType.bugfix)
        pending_release_update = models.Update(
            title=u'bodhi-2.3.2-1.fc25', builds=[pending_build], user=self.user,
            request=models.UpdateRequest.stable, notes=u'Useful details!', release=pending_release,
            date_submitted=datetime(2016, 10, 28), requirements=u'', stable_karma=3,
            unstable_karma=-3, type=models.UpdateType.bugfix)
        self.db.add(disabled_release_update)
        self.db.add(pending_release_update)
        query = self.db.query(models.Update)

        query = push._filter_releases(self.db, query)

        # Make sure the archived update didn't get in this business
        self.assertEqual(set([u.release.state for u in query]),
                         set([models.ReleaseState.current, models.ReleaseState.pending]))

    def test_one_release(self):
        """
        Test with one release.
        """
        query = self.db.query(models.Update)

        query = push._filter_releases(self.db, query, u'F22')

        # Make sure only F22 made it in.
        self.assertEqual([u.release.name for u in query], [u'F22'])

    def test_two_releases(self):
        """
        Test with two releases.
        """
        query = self.db.query(models.Update)

        query = push._filter_releases(self.db, query, u'F22,F17')

        # Make sure F17 and F22 made it in.
        self.assertEqual(set([u.release.name for u in query]), {u'F17', u'F22'})

    def test_unknown_release(self):
        """
        Ensure that we inform the user when they pass an unknown release.
        """
        query = self.db.query(models.Update)

        with self.assertRaises(click.BadParameter) as ex:
            push._filter_releases(self.db, query, u'RELEASE WITH NO NAME')
            self.assertEqual(str(ex.exception), 'Unknown release: RELEASE WITH NO NAME')
