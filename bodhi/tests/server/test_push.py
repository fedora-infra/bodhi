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

from click.testing import CliRunner
import click
import mock

from bodhi.server import push
from bodhi.server import models
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
        pkg = self.db.query(models.RpmPackage).filter_by(name=u'bodhi').one()
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
        pkg = self.db.query(models.RpmPackage).filter_by(name=u'bodhi').one()
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


TEST_ABORT_PUSH_EXPECTED_OUTPUT = """Warning: bodhi-2.0-1.fc17 is locked but not in a push
Warning: bodhi-2.0-1.fc17 has unsigned builds and has been skipped
python-nose-1.3.7-11.fc17
python-paste-deploy-1.5.2-8.fc17
Push these 2 updates? [y/N]: n
Aborted!
"""

TEST_BUILDS_FLAG_EXPECTED_OUTPUT = """ejabberd-16.09-4.fc17
python-nose-1.3.7-11.fc17
Push these 2 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_CERT_PREFIX_FLAG_EXPECTED_OUTPUT = """Warning: bodhi-2.0-1.fc17 is locked but not in a push
Warning: bodhi-2.0-1.fc17 has unsigned builds and has been skipped
python-nose-1.3.7-11.fc17
python-paste-deploy-1.5.2-8.fc17
Push these 2 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_LOCKED_UPDATES_EXPECTED_OUTPUT = """Warning: bodhi-2.0-1.fc17 is locked but not in a push
Warning: bodhi-2.0-1.fc17 has unsigned builds and has been skipped
python-nose-1.3.7-11.fc17
python-paste-deploy-1.5.2-8.fc17
Push these 2 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_LOCKED_UPDATES_NOT_IN_A_PUSH_EXPECTED_OUTPUT = """Warning: ejabberd-16.09-4.fc17 is locked but not in a push
python-nose-1.3.7-11.fc17
python-paste-deploy-1.5.2-8.fc17
ejabberd-16.09-4.fc17
Push these 3 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_NO_UPDATES_TO_PUSH_EXPECTED_OUTPUT = """Warning: python-nose-1.3.7-11.fc17 has unsigned builds and has been skipped
Warning: python-paste-deploy-1.5.2-8.fc17 has unsigned builds and has been skipped
Warning: bodhi-2.0-1.fc17 is locked but not in a push
Warning: bodhi-2.0-1.fc17 has unsigned builds and has been skipped

There are no updates to push.
"""

TEST_RELEASES_FLAG_EXPECTED_OUTPUT = """python-nose-1.3.7-11.fc25
python-paste-deploy-1.5.2-8.fc26
Push these 2 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_REQUEST_FLAG_EXPECTED_OUTPUT = """Warning: bodhi-2.0-1.fc17 is locked but not in a push
Warning: bodhi-2.0-1.fc17 has unsigned builds and has been skipped
python-paste-deploy-1.5.2-8.fc17
Push these 1 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_RESUME_FLAG_EXPECTED_OUTPUT = """Resume /mnt/koji/mash/updates/MASHING-f17-updates? [y/N]: y
ejabberd-16.09-4.fc17
Push these 1 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_RESUME_HUMAN_SAYS_NO_EXPECTED_OUTPUT = """Resume /mnt/koji/mash/updates/MASHING-f17-testing? [y/N]: n
Resume /mnt/koji/mash/updates/MASHING-f17-updates? [y/N]: y
ejabberd-16.09-4.fc17
Push these 1 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_STAGING_FLAG_EXPECTED_OUTPUT = """Warning: bodhi-2.0-1.fc17 is locked but not in a push
Warning: bodhi-2.0-1.fc17 has unsigned builds and has been skipped
python-nose-1.3.7-11.fc17
python-paste-deploy-1.5.2-8.fc17
Push these 2 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""

TEST_UNSIGNED_UPDATES_SKIPPED_EXPECTED_OUTPUT = """Warning: python-nose-1.3.7-11.fc17 has unsigned builds and has been skipped
Warning: bodhi-2.0-1.fc17 is locked but not in a push
Warning: bodhi-2.0-1.fc17 has unsigned builds and has been skipped
python-paste-deploy-1.5.2-8.fc17
Push these 1 updates? [y/N]: y

Locking updates...

Sending masher.start fedmsg
"""


class TestPush(base.BaseTestCase):
    """
    This class contains tests for the push() function.
    """
    def setUp(self):
        """
        Make some updates that can be pushed.
        """
        super(TestPush, self).setUp()
        python_nose = self.create_update([u'python-nose-1.3.7-11.fc17'])
        python_paste_deploy = self.create_update([u'python-paste-deploy-1.5.2-8.fc17'])
        # Make it so we have two builds to push out
        python_nose.builds[0].signed = True
        python_paste_deploy.builds[0].signed = True
        self.db.flush()

    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    def test_abort_push(self, publish):
        """
        Ensure that the push gets aborted if the user types 'n' when asked if they want to push.
        """
        cli = CliRunner()
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='n')

        # The exit code is 1 when the push is aborted.
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, TEST_ABORT_PUSH_EXPECTED_OUTPUT)
        self.assertEqual(publish.call_count, 0)

        # The updates should not be locked
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    def test_builds_flag(self, publish):
        """
        Assert correct operation when the --builds flag is given.
        """
        cli = CliRunner()
        ejabberd = self.create_update([u'ejabberd-16.09-4.fc17'])
        # Make it so we have three builds we could push out so that we can ask for and verify two
        ejabberd.builds[0].signed = True
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(
                push.push,
                ['--username', 'bowlofeggs', '--builds',
                 'python-nose-1.3.7-11.fc17,ejabberd-16.09-4.fc17'],
                input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_BUILDS_FLAG_EXPECTED_OUTPUT)
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': [u'ejabberd-16.09-4.fc17', u'python-nose-1.3.7-11.fc17'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)

        ejabberd = self.db.query(models.Update).filter_by(title=u'ejabberd-16.09-4.fc17').one()
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        for u in [ejabberd, python_nose]:
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())
        self.assertFalse(python_paste_deploy.locked)
        self.assertIsNone(python_paste_deploy.date_locked)

    @mock.patch('bodhi.server.push.bodhi.server.notifications.init')
    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    def test_cert_prefix_flag(self, publish, init):
        """
        Test correct operation when the --cert-prefix flag is used.
        """
        cli = CliRunner()
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(
                push.push, ['--username', 'bowlofeggs', '--cert-prefix', 'some_prefix'], input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_CERT_PREFIX_FLAG_EXPECTED_OUTPUT)
        init.assert_called_once_with(active=True, cert_prefix='some_prefix')
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['python-nose-1.3.7-11.fc17', u'python-paste-deploy-1.5.2-8.fc17'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)

    @mock.patch('bodhi.server.push.file', create=True)
    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.push.glob.glob',
                return_value=['/mnt/koji/mash/updates/MASHING-f17-updates'])
    @mock.patch('bodhi.server.push.json.load', return_value={'updates': ['ejabberd-16.09-4.fc17']})
    def test_locked_updates(self, load, glob, publish, mock_file):
        """
        Test correct operation when there are some locked updates.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. It should get silently ignored.
        ejabberd = self.create_update([u'ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        ejabberd.date_locked = datetime.utcnow()
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_LOCKED_UPDATES_EXPECTED_OUTPUT)
        glob.assert_called_once_with('/mnt/koji/mash/updates/MASHING-*')
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['python-nose-1.3.7-11.fc17', 'python-paste-deploy-1.5.2-8.fc17'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)
        mock_file.assert_called_once_with('/mnt/koji/mash/updates/MASHING-f17-updates')

        ejabberd = self.db.query(models.Update).filter_by(title=u'ejabberd-16.09-4.fc17').one()
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        for u in [ejabberd, python_nose, python_paste_deploy]:
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())

    @mock.patch('bodhi.server.push.file', create=True)
    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.push.glob.glob',
                return_value=['/mnt/koji/mash/updates/MASHING-f17-updates'])
    @mock.patch('bodhi.server.push.json.load', return_value={'updates': ['bodhi-2.0-1.fc17']})
    def test_locked_updates_not_in_a_push(self, load, glob, publish, mock_file):
        """
        Test correct operation when there are some locked updates that aren't in a push.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked but not already in a push. It should print a warning but
        # still get pushed.
        ejabberd = self.create_update([u'ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        ejabberd.date_locked = datetime.utcnow()
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='y')

        self.assertEqual(result.exit_code, 0)
        # The packages might be printed in any order and the order isn't important. So let's compare
        # the output with the package list removed to make sure that it is correct.
        self.assertEqual(
            '\n'.join([l for l in result.output.split('\n') if l[-4:] != 'fc17']),
            '\n'.join([l for l in TEST_LOCKED_UPDATES_NOT_IN_A_PUSH_EXPECTED_OUTPUT.split('\n')
                       if l[-4:] != 'fc17']))
        # Now let's assert that the package list is correct
        self.assertEqual(
            set([l for l in result.output.split('\n') if l[-4:] == 'fc17']),
            set([l for l in TEST_LOCKED_UPDATES_NOT_IN_A_PUSH_EXPECTED_OUTPUT.split('\n')
                 if l[-4:] == 'fc17']))
        glob.assert_called_once_with('/mnt/koji/mash/updates/MASHING-*')
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['python-nose-1.3.7-11.fc17', 'python-paste-deploy-1.5.2-8.fc17',
                             'ejabberd-16.09-4.fc17'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)
        mock_file.assert_called_once_with('/mnt/koji/mash/updates/MASHING-f17-updates')

        ejabberd = self.db.query(models.Update).filter_by(title=u'ejabberd-16.09-4.fc17').one()
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        for u in [ejabberd, python_nose, python_paste_deploy]:
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())

    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    def test_no_updates_to_push(self, publish):
        """
        If there are no updates to push, no push message should get sent.
        """
        cli = CliRunner()
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        python_nose.builds[0].signed = False
        python_paste_deploy.builds[0].signed = False
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_NO_UPDATES_TO_PUSH_EXPECTED_OUTPUT)
        self.assertEqual(publish.call_count, 0)

        # The updates should not be locked
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    def test_releases_flag(self, publish):
        """
        Assert correct operation from the --releases flag.
        """
        f25 = models.Release(
            name=u'F25', long_name=u'Fedora 25',
            id_prefix=u'FEDORA', version=u'25',
            dist_tag=u'f25', stable_tag=u'f25-updates',
            testing_tag=u'f25-updates-testing',
            candidate_tag=u'f25-updates-candidate',
            pending_signing_tag=u'f25-updates-testing-signing',
            pending_testing_tag=u'f25-updates-testing-pending',
            pending_stable_tag=u'f25-updates-pending',
            override_tag=u'f25-override',
            branch=u'f25', state=models.ReleaseState.current)
        f26 = models.Release(
            name=u'F26', long_name=u'Fedora 26',
            id_prefix=u'FEDORA', version=u'26',
            dist_tag=u'f26', stable_tag=u'f26-updates',
            testing_tag=u'f26-updates-testing',
            candidate_tag=u'f26-updates-candidate',
            pending_signing_tag=u'f26-updates-testing-signing',
            pending_testing_tag=u'f26-updates-testing-pending',
            pending_stable_tag=u'f26-updates-pending',
            override_tag=u'f26-override',
            branch=u'f26', state=models.ReleaseState.current)
        self.db.add(f25)
        self.db.add(f26)
        # Let's make an update for each release
        python_nose = self.create_update([u'python-nose-1.3.7-11.fc25'], u'F25')
        python_paste_deploy = self.create_update([u'python-paste-deploy-1.5.2-8.fc26'], u'F26')
        python_nose.builds[0].signed = True
        python_paste_deploy.builds[0].signed = True
        self.db.commit()
        cli = CliRunner()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            # We will specify that we want F25 and F26, which should exclude the F17 updates we've
            # been pushing in all the other tests. We'll leave the F off of 26 and lowercase the f
            # on 25 to make sure it's flexible.
            result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--releases', 'f25,26'],
                                input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RELEASES_FLAG_EXPECTED_OUTPUT)
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['python-nose-1.3.7-11.fc25', 'python-paste-deploy-1.5.2-8.fc26'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)

        # The Fedora 17 updates should not have been locked.
        f17_python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        f17_python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        self.assertFalse(f17_python_nose.locked)
        self.assertIsNone(f17_python_nose.date_locked)
        self.assertFalse(f17_python_paste_deploy.locked)
        self.assertIsNone(f17_python_paste_deploy.date_locked)
        # The new updates should both be locked.
        f25_python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc25').one()
        f26_python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc26').one()
        self.assertTrue(f25_python_nose.locked)
        self.assertTrue(f25_python_nose.date_locked <= datetime.utcnow())
        self.assertTrue(f26_python_paste_deploy.locked)
        self.assertTrue(f26_python_paste_deploy.date_locked <= datetime.utcnow())

    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    def test_request_flag(self, publish):
        """
        Assert that the --request flag works correctly.
        """
        cli = CliRunner()
        # Let's mark nose as a stable request so it gets excluded when we request a testing update.
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_nose.request = models.UpdateRequest.stable
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--request', 'testing'],
                                input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_REQUEST_FLAG_EXPECTED_OUTPUT)
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['python-paste-deploy-1.5.2-8.fc17'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)

        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        self.assertFalse(python_nose.locked)
        self.assertIsNone(python_nose.date_locked)
        self.assertTrue(python_paste_deploy.locked)
        self.assertTrue(python_paste_deploy.date_locked <= datetime.utcnow())

    @mock.patch('bodhi.server.push.file', create=True)
    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.push.glob.glob',
                return_value=['/mnt/koji/mash/updates/MASHING-f17-updates'])
    @mock.patch('bodhi.server.push.json.load', return_value={'updates': [u'ejabberd-16.09-4.fc17']})
    def test_resume_flag(self, load, glob, publish, mock_file):
        """
        Test correct operation when the --resume flag is given.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. Since we are resuming, it should be
        # the only package that gets included.
        ejabberd = self.create_update([u'ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        ejabberd.date_locked = datetime.utcnow()
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--resume'], input='y\ny')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RESUME_FLAG_EXPECTED_OUTPUT)
        glob.assert_called_once_with('/mnt/koji/mash/updates/MASHING-*')
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['ejabberd-16.09-4.fc17'],
                 'resume': True, 'agent': 'bowlofeggs'},
            force=True)
        mock_file.assert_called_once_with('/mnt/koji/mash/updates/MASHING-f17-updates')

        ejabberd = self.db.query(models.Update).filter_by(title=u'ejabberd-16.09-4.fc17').one()
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        # ejabberd should be locked still
        self.assertTrue(ejabberd.locked)
        self.assertTrue(ejabberd.date_locked <= datetime.utcnow())
        # The other packages should have been left alone
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    @mock.patch('bodhi.server.push.file', create=True)
    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.push.glob.glob',
                return_value=['/mnt/koji/mash/updates/MASHING-f17-testing',
                              '/mnt/koji/mash/updates/MASHING-f17-updates'])
    @mock.patch('bodhi.server.push.json.load',
                side_effect=[{'updates': [u'python-nose-1.3.7-11.fc17']},
                             {'updates': [u'ejabberd-16.09-4.fc17']}])
    def test_resume_human_says_no(self, load, glob, publish, mock_file):
        """
        Test correct operation when the --resume flag is given but the human says they don't want to
        resume one of the lockfiles.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. Since we are resuming and since we
        # will decline pushing the first time we are asked, it should be the only package that gets
        # included.
        ejabberd = self.create_update([u'ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        ejabberd.date_locked = datetime.utcnow()
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--resume'],
                                input='n\ny\ny')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RESUME_HUMAN_SAYS_NO_EXPECTED_OUTPUT)
        glob.assert_called_once_with('/mnt/koji/mash/updates/MASHING-*')
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['ejabberd-16.09-4.fc17'],
                 'resume': True, 'agent': 'bowlofeggs'},
            force=True)
        mock_file.assert_any_call('/mnt/koji/mash/updates/MASHING-f17-testing')
        mock_file.assert_any_call('/mnt/koji/mash/updates/MASHING-f17-updates')

        ejabberd = self.db.query(models.Update).filter_by(title=u'ejabberd-16.09-4.fc17').one()
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        # ejabberd should be locked still
        self.assertTrue(ejabberd.locked)
        self.assertTrue(ejabberd.date_locked <= datetime.utcnow())
        # The other packages should have been left alone
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    @mock.patch('bodhi.server.push.file', create=True)
    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.push.glob.glob',
                return_value=['/mnt/koji/mash/updates/MASHING-f17-updates'])
    @mock.patch('bodhi.server.push.json.load', return_value={'updates': [u'ejabberd-16.09-4.fc17']})
    def test_staging_flag(self, load, glob, publish, mock_file):
        """
        Test correct operation when the --staging flag is given. The main thing that matters is that
        the glob call happens on a different directory.
        """
        cli = CliRunner()
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--staging'], input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_STAGING_FLAG_EXPECTED_OUTPUT)
        glob.assert_called_once_with('/var/cache/bodhi/mashing/MASHING-*')
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['python-nose-1.3.7-11.fc17', u'python-paste-deploy-1.5.2-8.fc17'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)
        mock_file.assert_called_once_with('/mnt/koji/mash/updates/MASHING-f17-updates')

        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        # The packages should be locked
        for u in [python_nose, python_paste_deploy]:
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())

    @mock.patch('bodhi.server.push.bodhi.server.notifications.publish')
    def test_unsigned_updates_skipped(self, publish):
        """
        Unsigned updates should get skipped.
        """
        cli = CliRunner()
        # Let's mark nose unsigned so it gets skipped.
        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_nose.builds[0].signed = False
        self.db.commit()

        with mock.patch('bodhi.server.push.get_db_factory',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='y')

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_UNSIGNED_UPDATES_SKIPPED_EXPECTED_OUTPUT)
        publish.assert_called_once_with(
            topic='masher.start',
            msg={'updates': ['python-paste-deploy-1.5.2-8.fc17'],
                 'resume': False, 'agent': 'bowlofeggs'},
            force=True)

        python_nose = self.db.query(models.Update).filter_by(
            title=u'python-nose-1.3.7-11.fc17').one()
        python_paste_deploy = self.db.query(models.Update).filter_by(
            title=u'python-paste-deploy-1.5.2-8.fc17').one()
        self.assertFalse(python_nose.locked)
        self.assertIsNone(python_nose.date_locked)
        self.assertTrue(python_paste_deploy.locked)
        self.assertTrue(python_paste_deploy.date_locked <= datetime.utcnow())
