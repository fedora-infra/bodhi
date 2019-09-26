# Copyright © 2016-2019 Red Hat, Inc. and others.
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
"""This test suite contains tests on the bodhi.server.push module."""

from datetime import datetime
from unittest import mock

import click
from click.testing import CliRunner

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
            name='F22', long_name='Fedora 22',
            id_prefix='FEDORA', version='22',
            dist_tag='f22', stable_tag='f22-updates',
            testing_tag='f22-updates-testing',
            candidate_tag='f22-updates-candidate',
            pending_signing_tag='f22-updates-testing-signing',
            pending_testing_tag='f22-updates-testing-pending',
            pending_stable_tag='f22-updates-pending',
            override_tag='f22-override',
            branch='f22', state=models.ReleaseState.archived)
        self.db.add(archived_release)

        # Let's add an obscure package called bodhi to the release.
        pkg = self.db.query(models.RpmPackage).filter_by(name='bodhi').one()
        build = models.RpmBuild(nvr='bodhi-2.3.2-1.fc22', release=archived_release, package=pkg)
        self.db.add(build)

        # And an Update with the RpmBuild.
        self.archived_release_update = models.Update(
            builds=[build], user=self.user,
            request=models.UpdateRequest.stable, notes='Useful details!', release=archived_release,
            date_submitted=datetime(2016, 10, 28), requirements='', stable_karma=3,
            unstable_karma=-3, type=models.UpdateType.bugfix)
        self.db.add(self.archived_release_update)
        self.db.commit()

        test_config = base.original_config.copy()
        test_config['compose_dir'] = '/composedir/'
        mock_config = mock.patch.dict('bodhi.server.push.config', test_config)
        mock_config.start()
        self.addCleanup(mock_config.stop)

    def test_defaults_to_filtering_correct_releases(self):
        """
        Ensure that _filter_releases() filters out archived and disabled releases by default.
        """
        # To make sure the filter is skipping and including the right stuff, let's add a disabled
        # release and a pending release. Builds from the disabled one should be excluded and the
        # pending one should be included.
        disabled_release = models.Release(
            name='F21', long_name='Fedora 21',
            id_prefix='FEDORA', version='21',
            dist_tag='f21', stable_tag='f21-updates',
            testing_tag='f21-updates-testing',
            candidate_tag='f21-updates-candidate',
            pending_signing_tag='f21-updates-testing-signing',
            pending_testing_tag='f21-updates-testing-pending',
            pending_stable_tag='f21-updates-pending',
            override_tag='f21-override',
            branch='f21', state=models.ReleaseState.disabled)
        pending_release = models.Release(
            name='F25', long_name='Fedora 25',
            id_prefix='FEDORA', version='25',
            dist_tag='f25', stable_tag='f25-updates',
            testing_tag='f25-updates-testing',
            candidate_tag='f25-updates-candidate',
            pending_signing_tag='f25-updates-testing-signing',
            pending_testing_tag='f25-updates-testing-pending',
            pending_stable_tag='f25-updates-pending',
            override_tag='f25-override',
            branch='f25', state=models.ReleaseState.pending)
        self.db.add(disabled_release)
        self.db.add(pending_release)
        # Let's add the bodhi package to both releases.
        pkg = self.db.query(models.RpmPackage).filter_by(name='bodhi').one()
        disabled_build = models.RpmBuild(nvr='bodhi-2.3.2-1.fc21', release=disabled_release,
                                         package=pkg)
        pending_build = models.RpmBuild(nvr='bodhi-2.3.2-1.fc25', release=pending_release,
                                        package=pkg)
        self.db.add(disabled_build)
        self.db.add(pending_build)
        # Now let's create updates for both packages.
        disabled_release_update = models.Update(
            builds=[disabled_build], user=self.user,
            request=models.UpdateRequest.stable, notes='Useful details!', release=disabled_release,
            date_submitted=datetime(2016, 10, 28), requirements='', stable_karma=3,
            unstable_karma=-3, type=models.UpdateType.bugfix)
        pending_release_update = models.Update(
            builds=[pending_build], user=self.user,
            request=models.UpdateRequest.stable, notes='Useful details!', release=pending_release,
            date_submitted=datetime(2016, 10, 28), requirements='', stable_karma=3,
            unstable_karma=-3, type=models.UpdateType.bugfix)
        self.db.add(disabled_release_update)
        self.db.add(pending_release_update)
        self.db.commit()

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

        query = push._filter_releases(self.db, query, 'F17')

        # Make sure only F17 made it in.
        self.assertEqual([u.release.name for u in query], ['F17'])

    def test_two_releases(self):
        """
        Test with two releases.
        """
        # Create yet another release with 'current' state and update for it
        current_release = self.create_release('18')
        pkg = self.db.query(models.RpmPackage).filter_by(name='bodhi').one()
        current_build = models.RpmBuild(nvr='bodhi-2.3.2-1.fc18', release=current_release,
                                        package=pkg)
        self.db.add(current_build)
        current_release_update = models.Update(
            builds=[current_build], user=self.user,
            request=models.UpdateRequest.stable, notes='Useful details!', release=current_release,
            date_submitted=datetime(2016, 10, 28), requirements='', stable_karma=3,
            unstable_karma=-3, type=models.UpdateType.bugfix)
        self.db.add(current_release_update)
        self.db.commit()

        query = self.db.query(models.Update)
        query = push._filter_releases(self.db, query, 'F18,F17')

        # Make sure F17 and F18 made it in.
        self.assertEqual(set([u.release.name for u in query]), {'F17', 'F18'})

    def test_unknown_release(self):
        """
        Ensure that we inform the user when they pass an unknown release.
        """
        query = self.db.query(models.Update)

        with self.assertRaises(click.BadParameter) as ex:
            push._filter_releases(self.db, query, 'RELEASE WITH NO NAME')
            self.assertEqual(str(ex.exception), 'Unknown release: RELEASE WITH NO NAME')

    def test_archived_release(self):
        """
        Ensure that we inform the user when they pass archived release.
        """
        query = self.db.query(models.Update)

        with self.assertRaises(click.BadParameter) as ex:
            push._filter_releases(self.db, query, 'F22')
        self.assertEqual(
            str(ex.exception), 'Unknown release, or release not allowed to be composed: F22'
        )


TEST_ABORT_PUSH_EXPECTED_OUTPUT = """

===== <Compose: F17 testing> =====

python-nose-1.3.7-11.fc17
python-paste-deploy-1.5.2-8.fc17
bodhi-2.0-1.fc17


Push these 3 updates? [y/N]: n
Aborted!
"""

TEST_BUILDS_FLAG_EXPECTED_OUTPUT = """

===== <Compose: F17 testing> =====

ejabberd-16.09-4.fc17
python-nose-1.3.7-11.fc17


Push these 2 updates? [y/N]: y

Locking updates...

Requesting a compose
"""

TEST_YES_FLAG_EXPECTED_OUTPUT = """

===== <Compose: F17 testing> =====

python-nose-1.3.7-11.fc17
python-paste-deploy-1.5.2-8.fc17
bodhi-2.0-1.fc17


Pushing 3 updates.

Locking updates...

Requesting a compose
"""

TEST_LOCKED_UPDATES_EXPECTED_OUTPUT = """Existing composes detected: <Compose: F17 testing>. Do you wish to resume them all? [y/N]: y


===== <Compose: F17 testing> =====

ejabberd-16.09-4.fc17


Push these 1 updates? [y/N]: y

Locking updates...

Requesting a compose
"""

TEST_LOCKED_UPDATES_YES_FLAG_EXPECTED_OUTPUT = """Existing composes detected: <Compose: F17 testing>. Resuming all.


===== <Compose: F17 testing> =====

ejabberd-16.09-4.fc17


Pushing 1 updates.

Locking updates...

Requesting a compose
"""

TEST_RELEASES_FLAG_EXPECTED_OUTPUT = """

===== <Compose: F25 testing> =====

python-nose-1.3.7-11.fc25


===== <Compose: F26 testing> =====

python-paste-deploy-1.5.2-8.fc26


Push these 2 updates? [y/N]: y

Locking updates...

Requesting a compose
"""

TEST_REQUEST_FLAG_EXPECTED_OUTPUT = """

===== <Compose: F17 testing> =====

python-paste-deploy-1.5.2-8.fc17
bodhi-2.0-1.fc17


Push these 2 updates? [y/N]: y

Locking updates...

Requesting a compose
"""

TEST_RESUME_FLAG_EXPECTED_OUTPUT = """Resume <Compose: F17 testing>? [y/N]: y


===== <Compose: F17 testing> =====

ejabberd-16.09-4.fc17


Push these 1 updates? [y/N]: y

Locking updates...

Requesting a compose
"""

TEST_RESUME_AND_YES_FLAGS_EXPECTED_OUTPUT = """Resuming <Compose: F17 testing>.


===== <Compose: F17 testing> =====

ejabberd-16.09-4.fc17


Pushing 1 updates.

Locking updates...

Requesting a compose
"""

TEST_RESUME_EMPTY_COMPOSE = """Resume <Compose: F17 testing>? [y/N]: y
<Compose: F17 stable> has no updates. It is being removed.


===== <Compose: F17 testing> =====

ejabberd-16.09-4.fc17


Push these 1 updates? [y/N]: y

Locking updates...

Requesting a compose
"""

TEST_RESUME_HUMAN_SAYS_NO_EXPECTED_OUTPUT = """Resume <Compose: F17 testing>? [y/N]: y
Resume <Compose: F17 stable>? [y/N]: n


===== <Compose: F17 testing> =====

ejabberd-16.09-4.fc17


Push these 1 updates? [y/N]: y

Locking updates...

Requesting a compose
"""

TEST_BUILDS_AND_UPDATES_FLAG_EXPECTED_OUTPUT = """ERROR: Must specify only one of --updates or --builds
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
        python_nose = self.create_update(['python-nose-1.3.7-11.fc17'])
        python_paste_deploy = self.create_update(['python-paste-deploy-1.5.2-8.fc17'])
        # Make it so we have two builds to push out
        python_nose.builds[0].signed = True
        python_paste_deploy.builds[0].signed = True
        self.db.commit()

        test_config = base.original_config.copy()
        test_config['compose_dir'] = '/composedir/'
        mock_config = mock.patch.dict('bodhi.server.push.config', test_config)
        mock_config.start()
        self.addCleanup(mock_config.stop)

    def test_abort_push(self):
        """
        Ensure that the push gets aborted if the user types 'n' when asked if they want to push.
        """
        cli = CliRunner()
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='n')
                compose_task.delay.assert_not_called()

        # The exit code is 1 when the push is aborted.
        self.assertEqual(result.exit_code, 1)

        # This is a terribly dirty hack that strips an SQLAlchemy warning about calling configure
        # on a scoped session with existing sessions. This should ultimately be fixed by making
        # sure there are no sessions when the CLI is invoked (since it calls configure)
        if 'scoped session' in result.output:
            doctored_output = result.output.split('\n', 2)[2]
        else:
            doctored_output = result.output
        self.assertEqual(doctored_output, TEST_ABORT_PUSH_EXPECTED_OUTPUT)
        # The updates should not be locked
        for nvr in ['bodhi-2.0-1.fc17', 'python-nose-1.3.7-11.fc17',
                    'python-paste-deploy-1.5.2-8.fc17']:
            u = self.db.query(models.Build).filter_by(nvr=nvr).one().update
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    def test_builds_flag(self):
        """
        Assert correct operation when the --builds flag is given.
        """
        cli = CliRunner()
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        # Make it so we have three builds we could push out so that we can ask for and verify two
        ejabberd.builds[0].signed = True
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(
                    push.push,
                    ['--username', 'bowlofeggs', '--builds',
                     'python-nose-1.3.7-11.fc17,ejabberd-16.09-4.fc17'],
                    input='y')
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=False,
                    composes=[{'security': False, 'release_id': ejabberd.release.id,
                               'request': u'testing', 'content_type': u'rpm'}],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_BUILDS_FLAG_EXPECTED_OUTPUT)
        for nvr in ['ejabberd-16.09-4.fc17', 'python-nose-1.3.7-11.fc17']:
            u = self.db.query(models.Build).filter_by(nvr=nvr).one().update
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        self.assertFalse(python_paste_deploy.locked)
        self.assertIsNone(python_paste_deploy.date_locked)

    def test_updates_flag(self):
        """
        Assert correct operation when the --updates flag is given.
        """
        cli = CliRunner()
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        alias1 = ejabberd.alias
        u = self.db.query(models.Build).filter_by(nvr='python-nose-1.3.7-11.fc17').one().update
        alias2 = u.alias
        # Make it so we have three builds we could push out so that we can ask for and verify two
        ejabberd.builds[0].signed = True
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose:
                result = cli.invoke(
                    push.push,
                    ['--username', 'bowlofeggs', '--updates', alias1 + ',' + alias2],
                    input='y')
                self.assertTrue(compose.delay.called)
                compose_call = compose.delay.call_args_list[0][1]

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(compose_call["api_version"], 2)
        self.assertEqual(compose_call["composes"],
                         [{'security': False, 'release_id': ejabberd.release.id,
                           'request': 'testing', 'content_type': 'rpm'}])
        self.assertEqual(compose_call['resume'], False)
        self.assertEqual(compose_call['agent'], 'bowlofeggs')
        self.assertEqual(result.output, TEST_BUILDS_FLAG_EXPECTED_OUTPUT)
        for nvr in ['ejabberd-16.09-4.fc17', 'python-nose-1.3.7-11.fc17']:
            u = self.db.query(models.Build).filter_by(nvr=nvr).one().update
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        self.assertFalse(python_paste_deploy.locked)
        self.assertIsNone(python_paste_deploy.date_locked)

    def test_updates_and_builds_flag(self):
        """
        Assert correct operation when --builds and --updates flags are given.
        """
        cli = CliRunner()
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        alias = ejabberd.alias
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose:
                result = cli.invoke(
                    push.push,
                    ['--username', 'bowlofeggs', '--builds', 'python-nose-1.3.7-11.fc17',
                     '--updates', alias],
                    input='y')

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, TEST_BUILDS_AND_UPDATES_FLAG_EXPECTED_OUTPUT)
        self.assertFalse(compose.delay.called)
        for nvr in [
            'ejabberd-16.09-4.fc17',
            'python-nose-1.3.7-11.fc17',
            'python-paste-deploy-1.5.2-8.fc17',
        ]:
            u = self.db.query(models.Build).filter_by(nvr=nvr).one().update
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    def test_yes_flag(self):
        """
        Test correct operation when the --yes flag is used.
        """
        cli = CliRunner()
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(
                    push.push, ['--username', 'bowlofeggs', '--yes'])
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=False,
                    composes=[{'security': False, 'release_id': 1,
                               'request': u'testing', 'content_type': u'rpm'}],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_YES_FLAG_EXPECTED_OUTPUT)
        bodhi = self.db.query(models.Build).filter_by(
            nvr='bodhi-2.0-1.fc17').one().update
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        for u in [bodhi, python_nose, python_paste_deploy]:
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())
            self.assertEqual(u.compose.release.id, python_paste_deploy.release.id)
            self.assertEqual(u.compose.request, models.UpdateRequest.testing)
            self.assertEqual(u.compose.content_type, models.ContentType.rpm)

    def test_locked_updates(self):
        """
        Test correct operation when there are some locked updates.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. bodhi-push should prompt the user to
        # resume this compose rather than starting a new one.
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        compose = models.Compose(
            release=ejabberd.release, request=ejabberd.request, state=models.ComposeState.failed,
            error_message='y r u so mean nfs')
        self.db.add(compose)
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='y\ny')
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=True,
                    composes=[{'security': False, 'release_id': 1,
                               'request': u'testing', 'content_type': u'rpm'}],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_LOCKED_UPDATES_EXPECTED_OUTPUT)
        ejabberd = self.db.query(models.Build).filter_by(nvr='ejabberd-16.09-4.fc17').one().update
        self.assertTrue(ejabberd.locked)
        self.assertTrue(ejabberd.date_locked <= datetime.utcnow())
        self.assertEqual(ejabberd.compose.release, ejabberd.release)
        self.assertEqual(ejabberd.compose.request, ejabberd.request)
        self.assertEqual(ejabberd.compose.state, models.ComposeState.requested)
        self.assertEqual(ejabberd.compose.error_message, '')
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    def test_locked_updates_yes_flag(self):
        """
        Test correct operation when there are some locked updates and --yes flag is given.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. bodhi-push should resume this
        # compose.
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        compose = models.Compose(
            release=ejabberd.release, request=ejabberd.request, state=models.ComposeState.failed,
            error_message='y r u so mean nfs')
        self.db.add(compose)
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--yes'])
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=True,
                    composes=[ejabberd.compose.__json__(composer=True)],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_LOCKED_UPDATES_YES_FLAG_EXPECTED_OUTPUT)
        ejabberd = self.db.query(models.Build).filter_by(nvr='ejabberd-16.09-4.fc17').one().update
        self.assertTrue(ejabberd.locked)
        self.assertTrue(ejabberd.date_locked <= datetime.utcnow())
        self.assertEqual(ejabberd.compose.release, ejabberd.release)
        self.assertEqual(ejabberd.compose.request, ejabberd.request)
        self.assertEqual(ejabberd.compose.state, models.ComposeState.requested)
        self.assertEqual(ejabberd.compose.error_message, '')
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    def test_no_updates_to_push(self):
        """
        If there are no updates to push, no compose task should be requested.
        """
        cli = CliRunner()
        bodhi = self.db.query(models.Build).filter_by(
            nvr='bodhi-2.0-1.fc17').one().update
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        bodhi.builds[0].signed = False
        python_nose.builds[0].signed = False
        python_paste_deploy.builds[0].signed = False
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            # Note: this IS the signing-pending tag
            with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                            return_value=[{'name': 'f17-updates-testing-signing'}]):
                with mock.patch('bodhi.server.push.compose_task') as compose_task:
                    result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='y')
                    compose_task.delay.assert_not_called()

        self.assertEqual(result.exit_code, 0)
        # The updates should not be locked
        bodhi = self.db.query(models.Build).filter_by(
            nvr='bodhi-2.0-1.fc17').one().update
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)

    def test_releases_flag(self):
        """
        Assert correct operation from the --releases flag.
        """
        f25 = models.Release(
            name='F25', long_name='Fedora 25',
            id_prefix='FEDORA', version='25',
            dist_tag='f25', stable_tag='f25-updates',
            testing_tag='f25-updates-testing',
            candidate_tag='f25-updates-candidate',
            pending_signing_tag='f25-updates-testing-signing',
            pending_testing_tag='f25-updates-testing-pending',
            pending_stable_tag='f25-updates-pending',
            override_tag='f25-override',
            branch='f25', state=models.ReleaseState.current)
        f26 = models.Release(
            name='F26', long_name='Fedora 26',
            id_prefix='FEDORA', version='26',
            dist_tag='f26', stable_tag='f26-updates',
            testing_tag='f26-updates-testing',
            candidate_tag='f26-updates-candidate',
            pending_signing_tag='f26-updates-testing-signing',
            pending_testing_tag='f26-updates-testing-pending',
            pending_stable_tag='f26-updates-pending',
            override_tag='f26-override',
            branch='f26', state=models.ReleaseState.current)
        self.db.add(f25)
        self.db.add(f26)
        self.db.commit()
        # Let's make an update for each release
        python_nose = self.create_update(['python-nose-1.3.7-11.fc25'], 'F25')
        # Let's make nose a security update to test that its compose gets sorted first.
        python_nose.type = models.UpdateType.security
        python_paste_deploy = self.create_update(['python-paste-deploy-1.5.2-8.fc26'], 'F26')
        python_nose.builds[0].signed = True
        python_paste_deploy.builds[0].signed = True
        self.db.commit()
        cli = CliRunner()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                # We will specify that we want F25 and F26, which should exclude the F17 updates
                # we've been pushing in all the other tests. We'll leave the F off of 26 and
                # lowercase the f on 25 to make sure it's flexible.
                result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--releases', 'f25,26'],
                                    input='y')
                # The call to push modifies the database, so we need to modify the expected call to
                # suit.
                f25_python_nose = self.db.query(models.Build).filter_by(
                    nvr='python-nose-1.3.7-11.fc25').one().update
                f26_python_paste_deploy = self.db.query(models.Build).filter_by(
                    nvr='python-paste-deploy-1.5.2-8.fc26').one().update
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=False, composes=[
                        f25_python_nose.compose.__json__(composer=True),
                        f26_python_paste_deploy.compose.__json__(composer=True)
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RELEASES_FLAG_EXPECTED_OUTPUT)
        # The Fedora 17 updates should not have been locked.
        f17_python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        f17_python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        self.assertFalse(f17_python_nose.locked)
        self.assertIsNone(f17_python_nose.date_locked)
        self.assertIsNone(f17_python_nose.compose)
        self.assertFalse(f17_python_paste_deploy.locked)
        self.assertIsNone(f17_python_paste_deploy.date_locked)
        self.assertIsNone(f17_python_paste_deploy.compose)
        # The new updates should both be locked.
        self.assertTrue(f25_python_nose.locked)
        self.assertTrue(f25_python_nose.date_locked <= datetime.utcnow())
        self.assertTrue(f26_python_paste_deploy.locked)
        self.assertTrue(f26_python_paste_deploy.date_locked <= datetime.utcnow())
        # The new updates should also be associated with the new Composes.
        self.assertEqual(f25_python_nose.compose.release.id, f25.id)
        self.assertEqual(f25_python_nose.compose.request, models.UpdateRequest.testing)
        self.assertEqual(f26_python_paste_deploy.compose.release.id, f26.id)
        self.assertEqual(f26_python_paste_deploy.compose.request, models.UpdateRequest.testing)

    def test_create_composes_for_releases_marked_as_composed_by_bodhi(self):
        """
        Assert that composes are created only for releases marked as 'composed_by_bodhi'.
        """
        f25 = models.Release(
            name='F25', long_name='Fedora 25',
            id_prefix='FEDORA', version='25',
            dist_tag='f25', stable_tag='f25-updates',
            testing_tag='f25-updates-testing',
            candidate_tag='f25-updates-candidate',
            pending_signing_tag='f25-updates-testing-signing',
            pending_testing_tag='f25-updates-testing-pending',
            pending_stable_tag='f25-updates-pending',
            override_tag='f25-override',
            branch='f25', state=models.ReleaseState.current)
        f26 = models.Release(
            name='F26', long_name='Fedora 26',
            id_prefix='FEDORA', version='26',
            dist_tag='f26', stable_tag='f26-updates',
            testing_tag='f26-updates-testing',
            candidate_tag='f26-updates-candidate',
            pending_signing_tag='f26-updates-testing-signing',
            pending_testing_tag='f26-updates-testing-pending',
            pending_stable_tag='f26-updates-pending',
            override_tag='f26-override',
            branch='f26', state=models.ReleaseState.current)
        self.db.add(f25)
        self.db.add(f26)
        self.db.commit()
        # Let's make an update for each release
        python_nose = self.create_update(['python-nose-1.3.7-11.fc25'], 'F25')
        # Let's make nose a security update to test that its compose gets sorted first.
        python_nose.type = models.UpdateType.security
        python_paste_deploy = self.create_update(['python-paste-deploy-1.5.2-8.fc26'], 'F26')
        python_nose.builds[0].signed = True
        python_paste_deploy.builds[0].signed = True
        # Let's mark Fedora 17 release as not composed by Bodhi
        f17_release = self.db.query(models.Release).filter_by(
            name='F17').one()
        f17_release.composed_by_bodhi = False
        self.db.commit()
        cli = CliRunner()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs'], input='y')
                # Calling push alters the database, so we need to update the expected call to
                # reflect the changes.
                f25_python_nose = self.db.query(models.Build).filter_by(
                    nvr='python-nose-1.3.7-11.fc25').one().update
                f26_python_paste_deploy = self.db.query(models.Build).filter_by(
                    nvr='python-paste-deploy-1.5.2-8.fc26').one().update
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=False,
                    composes=[
                        f25_python_nose.compose.__json__(composer=True),
                        f26_python_paste_deploy.compose.__json__(composer=True)
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RELEASES_FLAG_EXPECTED_OUTPUT)
        # The Fedora 17 updates should not have been locked and composed.
        f17_python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        f17_python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        self.assertFalse(f17_python_nose.locked)
        self.assertIsNone(f17_python_nose.date_locked)
        self.assertIsNone(f17_python_nose.compose)
        self.assertFalse(f17_python_paste_deploy.locked)
        self.assertIsNone(f17_python_paste_deploy.date_locked)
        self.assertIsNone(f17_python_paste_deploy.compose)
        # The new updates should both be locked.
        self.assertTrue(f25_python_nose.locked)
        self.assertTrue(f25_python_nose.date_locked <= datetime.utcnow())
        self.assertTrue(f26_python_paste_deploy.locked)
        self.assertTrue(f26_python_paste_deploy.date_locked <= datetime.utcnow())
        # The new updates should also be associated with the new Composes.
        self.assertEqual(f25_python_nose.compose.release.id, f25.id)
        self.assertEqual(f25_python_nose.compose.request, models.UpdateRequest.testing)
        self.assertEqual(f26_python_paste_deploy.compose.release.id, f26.id)
        self.assertEqual(f26_python_paste_deploy.compose.request, models.UpdateRequest.testing)

    def test_request_flag(self):
        """
        Assert that the --request flag works correctly.
        """
        cli = CliRunner()
        # Let's mark nose as a stable request so it gets excluded when we request a testing update.
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_nose.request = models.UpdateRequest.stable
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--request', 'testing'],
                                    input='y')
                # The call to push modifies the database, so we need to modify the expected call to
                # suit.
                bodhi = self.db.query(models.Build).filter_by(
                    nvr='bodhi-2.0-1.fc17').one().update
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=False, composes=[
                        bodhi.compose.__json__(composer=True)
                    ],
                )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, TEST_REQUEST_FLAG_EXPECTED_OUTPUT)
            python_nose = self.db.query(models.Build).filter_by(
                nvr='python-nose-1.3.7-11.fc17').one().update
            python_paste_deploy = self.db.query(models.Build).filter_by(
                nvr='python-paste-deploy-1.5.2-8.fc17').one().update
            self.assertFalse(python_nose.locked)
            self.assertIsNone(python_nose.date_locked)
            self.assertIsNone(python_nose.compose)
            for u in [bodhi, python_paste_deploy]:
                self.assertTrue(u.locked)
                self.assertTrue(u.date_locked <= datetime.utcnow())
                self.assertEqual(u.compose.release.id, python_paste_deploy.release.id)
                self.assertEqual(u.compose.request, models.UpdateRequest.testing)
                self.assertEqual(u.compose.content_type, models.ContentType.rpm)

    def test_resume_flag(self):
        """
        Test correct operation when the --resume flag is given.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. Since we are resuming, it should be
        # the only package that gets included.
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        compose = models.Compose(release=ejabberd.release, request=ejabberd.request)
        self.db.add(compose)
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--resume'],
                                    input='y\ny')
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=True,
                    composes=[ejabberd.compose.__json__(composer=True)],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RESUME_FLAG_EXPECTED_OUTPUT)
        ejabberd = self.db.query(models.Build).filter_by(nvr='ejabberd-16.09-4.fc17').one().update
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        # ejabberd should be locked still
        self.assertTrue(ejabberd.locked)
        self.assertTrue(ejabberd.date_locked <= datetime.utcnow())
        self.assertEqual(ejabberd.compose.release, ejabberd.release)
        self.assertEqual(ejabberd.compose.request, ejabberd.request)
        # The other packages should have been left alone
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)
            self.assertIsNone(u.compose)

    def test_resume_and_yes_flags(self):
        """
        Test correct operation when the --resume flag and --yes flag are given.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. Since we are resuming, it should be
        # the only package that gets included.
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        compose = models.Compose(release=ejabberd.release, request=ejabberd.request)
        self.db.add(compose)
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--resume', '--yes'])
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=True,
                    composes=[ejabberd.compose.__json__(composer=True)],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RESUME_AND_YES_FLAGS_EXPECTED_OUTPUT)
        ejabberd = self.db.query(models.Build).filter_by(nvr='ejabberd-16.09-4.fc17').one().update
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        # ejabberd should be locked still
        self.assertTrue(ejabberd.locked)
        self.assertTrue(ejabberd.date_locked <= datetime.utcnow())
        self.assertEqual(ejabberd.compose.release, ejabberd.release)
        self.assertEqual(ejabberd.compose.request, ejabberd.request)
        # The other packages should have been left alone
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)
            self.assertIsNone(u.compose)

    def test_resume_empty_compose(self):
        """
        Test correct operation when the --resume flag is given but one of the Composes has no
        updates.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. Since we are resuming and since we
        # will decline pushing the first time we are asked, it should be the only package that gets
        # included.
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        compose = models.Compose(release=ejabberd.release, request=ejabberd.request)
        self.db.add(compose)
        # This compose has no updates, so bodhi-push should delete it.
        compose = models.Compose(release=ejabberd.release, request=models.UpdateRequest.stable)
        self.db.add(compose)
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--resume'],
                                    input='y\ny')
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=True,
                    composes=[ejabberd.compose.__json__(composer=True)],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RESUME_EMPTY_COMPOSE)
        ejabberd = self.db.query(models.Build).filter_by(nvr='ejabberd-16.09-4.fc17').one().update
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        # ejabberd should still be locked.
        self.assertTrue(ejabberd.locked)
        self.assertTrue(ejabberd.date_locked <= datetime.utcnow())
        self.assertEqual(ejabberd.compose.release, ejabberd.release)
        self.assertEqual(ejabberd.compose.request, ejabberd.request)
        # These should be left alone.
        for u in [python_nose, python_paste_deploy]:
            self.assertFalse(u.locked)
            self.assertIsNone(u.date_locked)
            self.assertIsNone(u.compose)
        # The empty compose should have been deleted.
        self.assertEqual(
            self.db.query(models.Compose).filter_by(
                release_id=ejabberd.release.id, request=models.UpdateRequest.stable).count(),
            0)

    def test_resume_human_says_no(self):
        """
        Test correct operation when the --resume flag is given but the human says they don't want to
        resume one of the lockfiles.
        """
        cli = CliRunner()
        # Let's mark ejabberd as locked and already in a push. Since we are resuming and since we
        # will decline pushing the first time we are asked, it should be the only package that gets
        # included.
        ejabberd = self.create_update(['ejabberd-16.09-4.fc17'])
        ejabberd.builds[0].signed = True
        ejabberd.locked = True
        compose = models.Compose(release=ejabberd.release, request=ejabberd.request)
        self.db.add(compose)
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_nose.locked = True
        python_nose.request = models.UpdateRequest.stable
        compose = models.Compose(release=python_nose.release, request=python_nose.request)
        self.db.add(compose)
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            with mock.patch('bodhi.server.push.compose_task') as compose_task:
                result = cli.invoke(push.push, ['--username', 'bowlofeggs', '--resume'],
                                    input='y\nn\ny')
                compose_task.delay.assert_called_with(
                    api_version=2, agent="bowlofeggs", resume=True,
                    composes=[ejabberd.compose.__json__(composer=True)],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, TEST_RESUME_HUMAN_SAYS_NO_EXPECTED_OUTPUT)
        ejabberd = self.db.query(models.Build).filter_by(nvr='ejabberd-16.09-4.fc17').one().update
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_paste_deploy = self.db.query(models.Build).filter_by(
            nvr='python-paste-deploy-1.5.2-8.fc17').one().update
        # These should still be locked.
        for u in [ejabberd, python_nose]:
            self.assertTrue(u.locked)
            self.assertTrue(u.date_locked <= datetime.utcnow())
            self.assertEqual(u.compose.release, u.release)
            self.assertEqual(u.compose.request, u.request)
        # paste_deploy should have been left alone
        self.assertFalse(python_paste_deploy.locked)
        self.assertIsNone(python_paste_deploy.date_locked)
        self.assertIsNone(python_paste_deploy.compose)

    def test_unsigned_updates_unsigned_skipped(self):
        """
        Unsigned updates should get skipped.
        """
        cli = CliRunner()
        # Let's mark nose unsigned so it gets skipped.
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_nose.builds[0].signed = False
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            # Note: this IS the signing-pending tag
            with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                            return_value=[{'name': 'f17-updates-testing-signing'}]):
                with mock.patch('bodhi.server.push.compose_task') as compose_task:
                    result = cli.invoke(push.push, ['--username', 'bowlofeggs'],
                                        input='y')
                    # The call to push modifies the database, so we need to modify the expected call
                    # to suit.
                    python_paste_deploy = self.db.query(models.Build).filter_by(
                        nvr='python-paste-deploy-1.5.2-8.fc17').one().update
                    compose_task.delay.assert_called_with(
                        api_version=2, agent="bowlofeggs", resume=False, composes=[
                            python_paste_deploy.compose.__json__(composer=True)
                        ],
                    )

        self.assertIn(
            f'Warning: {python_nose.get_title()} has unsigned builds and has been skipped',
            result.output)
        self.assertEqual(result.exception, None)
        self.assertEqual(result.exit_code, 0)
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        self.assertFalse(python_nose.locked)
        self.assertIsNone(python_nose.date_locked)
        self.assertTrue(python_paste_deploy.locked)
        self.assertTrue(python_paste_deploy.date_locked <= datetime.utcnow())
        self.assertEqual(python_paste_deploy.compose.release, python_paste_deploy.release)
        self.assertEqual(python_paste_deploy.compose.request, python_paste_deploy.request)

    def test_unsigned_updates_signed_updated(self):
        """
        Unsigned updates should get marked signed.
        """
        cli = CliRunner()
        # Let's mark nose unsigned so it gets marked signed.
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        python_nose.builds[0].signed = False
        self.db.commit()

        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=base.TransactionalSessionMaker(self.Session)):
            # Note: this is NOT the signing-pending tag
            with mock.patch('bodhi.server.buildsys.DevBuildsys.listTags',
                            return_value=[{'name': 'f17-updates-testing'}]):
                with mock.patch('bodhi.server.push.compose_task') as compose_task:
                    result = cli.invoke(push.push, ['--username', 'bowlofeggs'],
                                        input='y')
                    # The call to push modifies the database, so we need to modify the expected call
                    # to suit.
                    python_paste_deploy = self.db.query(models.Build).filter_by(
                        nvr='python-paste-deploy-1.5.2-8.fc17').one().update
                    compose_task.delay.assert_called_with(
                        api_version=2, agent="bowlofeggs", resume=False, composes=[
                            python_paste_deploy.compose.__json__(composer=True)

                        ],
                    )

        self.assertEqual(result.exception, None)
        self.assertEqual(result.exit_code, 0)
        python_nose = self.db.query(models.Build).filter_by(
            nvr='python-nose-1.3.7-11.fc17').one().update
        self.assertTrue(python_nose.locked)
        self.assertTrue(python_nose.date_locked <= datetime.utcnow())
        self.assertEqual(python_nose.compose.release, python_paste_deploy.release)
        self.assertEqual(python_nose.compose.request, python_paste_deploy.request)
        self.assertTrue(python_paste_deploy.locked)
        self.assertTrue(python_paste_deploy.date_locked <= datetime.utcnow())
        self.assertEqual(python_paste_deploy.compose.release, python_paste_deploy.release)
        self.assertEqual(python_paste_deploy.compose.request, python_paste_deploy.request)


class TetUpdateSigStatus(base.BaseTestCase):
    """Test the update_sig_status() function."""

    @mock.patch.dict('bodhi.server.push.config',
                     {'buildsystem': 'koji', 'koji_hub': 'https://example.com/koji'})
    @mock.patch('bodhi.server.buildsys._buildsystem', None)
    @mock.patch('bodhi.server.buildsys.koji.ClientSession.krb_login')
    def test_sets_up_buildsys_without_auth(self, krb_login):
        """
        bodhi-push should not set up authentication for the build system.

        https://github.com/fedora-infra/bodhi/issues/2190
        """
        u = self.db.query(models.Update).first()

        push.update_sig_status(u)

        self.assertEqual(krb_login.call_count, 0)
