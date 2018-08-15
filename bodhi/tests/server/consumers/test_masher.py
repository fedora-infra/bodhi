# -*- coding: utf-8 -*-
# Copyright © 2007-2018 Red Hat, Inc.
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
import datetime
import dummy_threading
import errno
import json
import os
import shutil
import tempfile
import time
import unittest

from click import testing
import mock
import six
import six.moves.urllib.parse as urlparse
from six.moves.urllib.error import HTTPError, URLError
from six import StringIO

from bodhi.server import buildsys, exceptions, log, push
from bodhi.server.config import config
from bodhi.server.consumers.masher import (
    checkpoint, Masher, ComposerThread, ContainerComposerThread, RPMComposerThread,
    ModuleComposerThread, PungiComposerThread)
from bodhi.server.exceptions import LockedUpdateException
from bodhi.server.models import (
    Build, BuildrootOverride, Compose, ComposeState, ContainerBuild, Release, ReleaseState,
    RpmBuild, TestGatingStatus, Update, UpdateRequest, UpdateStatus, UpdateType, User, ModuleBuild,
    ContentType, Package)
from bodhi.server.util import mkmetadatadir
from bodhi.tests.server import base


mock_exc = mock.Mock()
mock_exc.side_effect = Exception


mock_taskotron_results = {
    'target': 'bodhi.server.util.taskotron_results',
    'return_value': [{
        "outcome": "PASSED",
        "data": {},
        "testcase": {"name": "rpmlint"}
    }],
}

mock_failed_taskotron_results = {
    'target': 'bodhi.server.util.taskotron_results',
    'return_value': [{
        "outcome": "FAILED",
        "data": {},
        "testcase": {"name": "rpmlint"}
    }],
}

mock_absent_taskotron_results = {
    'target': 'bodhi.server.util.taskotron_results',
    'return_value': [],
}


class FakeHub(object):
    def __init__(self):
        self.config = {
            'topic_prefix': 'org.fedoraproject',
            'environment': 'dev',
            'releng_fedmsg_certname': None,
            'masher_topic': 'bodhi.start',
            'masher': True,
            'validate_signatures': False,
        }

    def subscribe(self, *args, **kw):
        pass


class TestCheckpoint(unittest.TestCase):
    """Test the checkpoint() decorator."""
    def test_with_return(self):
        """checkpoint() should raise a ValueError if the wrapped function returns anything."""
        class TestClass(object):
            def __init__(self):
                self.resume = False

            @checkpoint
            def dont_wrap_me_bro(self):
                return "I told you not to do this. Now look what happened."

        with self.assertRaises(ValueError) as exc:
            TestClass().dont_wrap_me_bro()

        self.assertEqual(str(exc.exception), 'checkpointed functions may not return stuff')


@mock.patch('bodhi.server.push.initialize_db', mock.MagicMock())
@mock.patch('bodhi.server.push.bodhi.server.notifications.init', mock.MagicMock())
def _make_msg(transactional_session_maker, extra_push_args=None):
    """
    Use bodhi-push to start a compose, and return the fedmsg that bodhi-push sends.

    Args:
        transactional_session_maker (object): A context manager to use to get a db session.
        extra_push_args (list): A list of extra arguments to pass to bodhi-push.
    Returns:
        dict: A dictionary of the fedmsg that bodhi-push sends.
    """
    if extra_push_args is None:
        extra_push_args = []
    cli = testing.CliRunner()

    with mock.patch('bodhi.server.push.bodhi.server.notifications.publish') as publish:
        with mock.patch('bodhi.server.push.transactional_session_maker',
                        return_value=transactional_session_maker):
            cli.invoke(push.push, ['--username', 'bowlofeggs'] + extra_push_args, input='y\ny')

    return {'body': publish.mock_calls[0][2]}


# We don't need real pungi config files, we just need them to exist. Let's also mock all calls to
# pungi.
@mock.patch.dict(
    config,
    {'pungi.basepath': os.path.join(
        base.PROJECT_PATH, 'bodhi/tests/server/consumers/pungi.basepath'),
     'pungi.cmd': '/usr/bin/true'})
class TestMasher(base.BaseTestCase):

    def setUp(self):
        super(TestMasher, self).setUp()
        self._new_mash_stage_dir = tempfile.mkdtemp()

        # Since the ComposerThread is a subclass of Thread and since it is already constructed
        # before we have a chance to alter it, we need to change its superclass to be
        # dummy_threading.Thread so that the test suite doesn't launch real Threads. Threads cannot
        # use the same database sessions, and that means that changes that threads make will not
        # appear in other thread's sessions, which cause a lot of problems in these tests.
        # Mock was not able to make this change since the __bases__ attribute cannot be removed, but
        # we don't really need this to be cleaned up since we don't want any tests launching theads
        # anyway.
        ComposerThread.__bases__ = (dummy_threading.Thread,)
        test_config = base.original_config.copy()
        test_config['mash_stage_dir'] = self._new_mash_stage_dir
        test_config['mash_dir'] = os.path.join(self._new_mash_stage_dir, 'mash')

        mock_config = mock.patch.dict(
            'bodhi.server.consumers.masher.config', test_config)
        mock_config.start()
        self.addCleanup(mock_config.stop)

        os.makedirs(os.path.join(self._new_mash_stage_dir, 'mash'))

        self.koji = buildsys.get_session()
        self.koji.clear()  # clear out our dev introspection

        self.tempdir = tempfile.mkdtemp('bodhi')
        self.db_factory = base.TransactionalSessionMaker(self.Session)
        self.masher = Masher(FakeHub(), db_factory=self.db_factory, mash_dir=self.tempdir)

        # Reset "cached" objects before each test.
        Release._all_releases = None
        Release._tag_cache = None

        self.expected_sems = 0
        self.semmock = mock.MagicMock()
        self.masher.max_mashes_sem = self.semmock

    def tearDown(self):
        super(TestMasher, self).tearDown()

        self.assert_sems(self.expected_sems)

        shutil.rmtree(self.tempdir)
        shutil.rmtree(self._new_mash_stage_dir)

    def assert_sems(self, nr_expected):
        assert self.semmock.acquire.call_count == nr_expected
        assert self.semmock.release.call_count == self.semmock.acquire.call_count

    def set_stable_request(self, title):
        with self.db_factory() as session:
            query = session.query(Update).filter_by(title=title)
            update = query.one()
            update.request = UpdateRequest.stable
            session.flush()

    def _generate_fake_pungi(self, masher_thread, tag, release, empty=False, noarches=False):
        """
        Return a function that is suitable for mock to replace the call to Popen that run Pungi.

        Args:
            masher_thread (bodhi.server.consumers.masher.ComposerThread): The ComposerThread that
                Pungi is running inside.
            tag (basestring): The type of tag you wish to mash ("stable_tag" or "testing_tag").
            release (bodhi.server.models.Release): The Release you are mashing.
            empty (bool): Whether to make an empty folder.
            noarches (bool): Whether to create a base compose dir without arches.
        Returns:
            method: A fake Pungi subprocess that will create some basic repo files and folders for
                testing.
        """
        def fake_pungi(*args, **kwargs):
            """
            Create some test files/folders and return a fake Popen() return MagicMock.

            Returns:
                mock.MagicMock: A fake return value suitable for Popen().
            """
            fake_repodata = '''<?xml version="1.0" encoding="UTF-8"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo"
    xmlns:rpm="http://linux.duke.edu/metadata/rpm">
<revision>1508375628</revision></repomd>'''

            # We need to fake Pungi having run or _wait_for_pungi() will fail to find the output dir
            reqtype = 'updates' if tag == 'stable_tag' else 'updates-testing'
            d = datetime.datetime.utcnow()
            mash_dir = os.path.join(
                masher_thread.mash_dir,
                '%s-%d-%s-%s%02d%02d.0' % (release.id_prefix.title(),
                                           int(release.version),
                                           reqtype,
                                           d.year,
                                           d.month,
                                           d.day))

            if not empty:
                os.makedirs(os.path.join(mash_dir, 'compose', 'Everything'))

            if not noarches:
                for arch in ('i386', 'x86_64', 'armhfp'):
                    arch_repo = os.path.join(mash_dir, 'compose', 'Everything', arch)
                    repodata = os.path.join(arch_repo, 'os', 'repodata')
                    os.makedirs(repodata)
                    os.makedirs(os.path.join(arch_repo, 'debug/tree/Packages'))
                    os.makedirs(os.path.join(arch_repo, 'os/Packages'))
                    with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                        repomd.write(fake_repodata)

                source_repo = os.path.join(mash_dir, 'compose', 'Everything', 'source')
                repodata = os.path.join(source_repo, 'tree', 'repodata')
                os.makedirs(repodata)
                os.makedirs(os.path.join(source_repo, 'tree', 'Packages'))
                with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                    repomd.write(fake_repodata)

            os.makedirs(os.path.join(mash_dir, 'compose', 'metadata'))
            with open(os.path.join(mash_dir, 'compose', 'metadata', 'composeinfo.json'), 'w') as f:
                f.write('{}')

            fake_stdout = '''Some output
Some more output ...... This is not a Compose dir: ....
Compose dir: %s
That was the actual one''' % mash_dir

            fake_popen = mock.MagicMock()
            fake_popen.communicate = lambda: (fake_stdout, 'hello')
            fake_popen.poll.return_value = None
            fake_popen.returncode = 0
            return fake_popen

        return fake_pungi

    def _make_msg(self, extra_push_args=None):
        """
        Use bodhi-push to start a compose, and return the fedmsg that bodhi-push sends.

        Returns:
            dict: A dictionary of the fedmsg that bodhi-push sends.
        """
        return _make_msg(self.db_factory, extra_push_args)

    @mock.patch('bodhi.server.consumers.masher.bugs.set_bugtracker')
    def test___init___sets_bugtracker(self, set_bugtracker):
        """
        Assert that Masher.__init__() calls bodhi.server.bugs.set_bugtracker().
        """
        Masher(FakeHub(), db_factory=self.db_factory, mash_dir=self.tempdir)

        set_bugtracker.assert_called_once_with()

    @mock.patch.dict('bodhi.server.config.config', {'pungi.cmd': '/does/not/exist'})
    def test___init___missing_paths(self):
        """__init__() should raise a ValueError if configured paths do not exist."""
        for s in ('pungi.cmd', 'mash_dir', 'mash_stage_dir'):
            with mock.patch.dict('bodhi.server.config.config', {s: '/does/not/exist'}):
                with self.assertRaises(ValueError) as exc:
                    Masher(FakeHub(), db_factory=self.db_factory, mash_dir=self.tempdir)

                    self.assertEqual(
                        str(exc.exception),
                        '"/does/not/exist" does not exist. Check the {} setting.'.format(s))

    @mock.patch('bodhi.server.consumers.masher.initialize_db')
    @mock.patch('bodhi.server.consumers.masher.transactional_session_maker')
    def test___init___without_db_factory(self, transactional_session_maker, initialize_db):
        """__init__() should make its own db_factory if not given one."""
        m = Masher(FakeHub(), mash_dir=self.tempdir)

        self.assertEqual(m.db_factory, transactional_session_maker.return_value)
        initialize_db.assert_called_once_with(config)
        transactional_session_maker.assert_called_once_with()

    def test__get_composes_api_1(self):
        """Test _get_composes() with API version 1 (which isn't explicit about its version)."""
        with self.db_factory() as db:
            msg = {'resume': False, 'agent': u'bowlofeggs',
                   'updates': [db.query(Update).one().title]}

        composes = self.masher._get_composes(msg)

        self.assertEqual(len(composes), 1)
        with self.db_factory() as db:
            compose = Compose.from_dict(db, composes[0])
            self.assertEqual(
                composes,
                [{'content_type': compose.content_type.value, 'release_id': compose.release.id,
                  'request': compose.request.value, 'security': compose.security}])
            self.assertEqual(compose.state, ComposeState.pending)
            self.assertEqual(compose.updates, [db.query(Update).one()])

    def test__get_composes_api_2(self):
        """Test _get_composes() with API version 2."""
        composes = self.masher._get_composes(self._make_msg()['body']['msg'])

        self.assertEqual(len(composes), 1)
        with self.db_factory() as db:
            compose = Compose.from_dict(db, composes[0])
            self.assertEqual(
                composes,
                [{'content_type': compose.content_type.value, 'release_id': compose.release.id,
                  'request': compose.request.value, 'security': compose.security}])
            self.assertEqual(compose.state, ComposeState.pending)

    def test__get_composes_api_3(self):
        """Test _get_composes() with API version 3, which is currently unsupported."""
        msg = self._make_msg()['body']['msg']
        msg['api_version'] = 3

        with self.assertRaises(ValueError) as exc:
            self.masher._get_composes(msg)

        self.assertEqual(str(exc.exception), 'Unable to process fedmsg: {}'.format(msg))
        with self.db_factory() as db:
            compose = db.query(Compose).one()
            # The Compose's state should not have been altered.
            self.assertEqual(compose.state, ComposeState.requested)

    @mock.patch('bodhi.server.notifications.publish')
    def test_invalid_signature(self, publish):
        """Make sure the masher ignores messages that aren't signed with the
        appropriate releng cert
        """
        fakehub = FakeHub()
        fakehub.config['releng_fedmsg_certname'] = 'foo'
        self.masher = Masher(fakehub, db_factory=self.db_factory)
        self.masher.consume(self._make_msg())

        # The masher should not have unlocked the Update.
        with self.db_factory() as session:
            # Ensure that the update was locked
            up = session.query(Update).one()
            self.assertTrue(up.locked)

        # Ensure mashtask.start never got sent
        self.assertEqual(len(publish.call_args_list), 0)

    @mock.patch('bodhi.server.notifications.publish')
    def test_push_invalid_compose(self, publish):
        msg = self._make_msg()
        msg['body']['msg']['composes'][0]['release_id'] = 65535

        with self.assertRaises(Exception) as exc:
            self.masher.consume(msg)

        self.assertEqual(str(exc.exception), 'No row was found for one()')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch.object(ComposerThread, 'determine_and_perform_tag_actions', mock_exc)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_locking(self, publish, *args):
        self.expected_sems = 1

        with self.db_factory() as session:
            up = session.query(Update).one()
            up.locked = False

        self.masher.consume(self._make_msg())

        # Ensure that fedmsg was called 4 times
        self.assertEqual(len(publish.call_args_list), 3)

        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=False,
                     ctype='rpm',
                     repo='f17-updates-testing',
                     agent='bowlofeggs'),
            force=True)

        with self.db_factory() as session:
            # Ensure that the update was locked
            up = session.query(Update).one()
            self.assertTrue(up.locked)

            # Ensure we can't set a request
            try:
                up.set_request(session, UpdateRequest.stable, u'bodhi')
                assert False, 'Set the request on a locked update'
            except LockedUpdateException:
                pass

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_tags(self, publish, *args):
        self.expected_sems = 2

        # Make the build a buildroot override as well
        with self.db_factory() as session:
            release = session.query(Update).one().release
            build = session.query(Build).one()
            nvr = build.nvr
            pending_signing_tag = release.pending_signing_tag
            pending_testing_tag = release.pending_testing_tag
            override_tag = release.override_tag
            self.koji.__tagged__[session.query(Update).first().title] = [release.override_tag,
                                                                         pending_testing_tag]

        # Start the push
        self.masher.consume(self._make_msg())

        # Ensure that fedmsg was called 3 times
        self.assertEqual(len(publish.call_args_list), 4)
        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=True,
                     ctype='rpm',
                     repo='f17-updates-testing',
                     agent='bowlofeggs'),
            force=True)

        # Ensure our single update was moved
        self.assertEqual(len(self.koji.__moved__), 1)
        self.assertEqual(len(self.koji.__added__), 0)
        self.assertEqual(self.koji.__moved__[0],
                         (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-1.fc17'))

        # The override tag won't get removed until it goes to stable
        self.assertEqual(self.koji.__untag__[0], (pending_signing_tag, nvr))
        self.assertEqual(self.koji.__untag__[1], (pending_testing_tag, nvr))
        self.assertEqual(len(self.koji.__untag__), 2)

        with self.db_factory() as session:
            # Set the update request to stable and the release to pending
            up = session.query(Update).one()
            up.release.state = ReleaseState.pending
            up.request = UpdateRequest.stable

        self.koji.clear()

        self.masher.consume(self._make_msg())

        # Ensure that stable updates to pending releases get their
        # tags added, not removed
        self.assertEqual(len(self.koji.__moved__), 0)
        self.assertEqual(len(self.koji.__added__), 1)
        self.assertEqual(self.koji.__added__[0], (u'f17', u'bodhi-2.0-1.fc17'))
        self.assertEqual(self.koji.__untag__[0], (override_tag, u'bodhi-2.0-1.fc17'))

        # Check that the override got expired
        with self.db_factory() as session:
            ovrd = session.query(BuildrootOverride).one()
            self.assertIsNotNone(ovrd.expired_date)

            # Check that the request_complete method got run
            up = session.query(Update).one()
            self.assertIsNone(up.request)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_tag_ordering(self, publish, *args):
        """
        Test pushing a batch of updates with multiple builds for the same package.
        Ensure that the latest version is tagged last.
        """
        self.expected_sems = 1
        otherbuild = u'bodhi-2.0-2.fc17'

        with self.db_factory() as session:
            firstupdate = session.query(Update).one()
            build = RpmBuild(nvr=otherbuild, package=firstupdate.builds[0].package, signed=True)
            session.add(build)
            update = Update(
                title=otherbuild, builds=[build], type=UpdateType.bugfix,
                request=UpdateRequest.testing, notes=u'second update', user=firstupdate.user)
            update.release = firstupdate.release
            session.add(update)
            session.flush()

        # Start the push
        self.masher.consume(self._make_msg())

        # Ensure that fedmsg was called 5 times
        self.assertEqual(len(publish.call_args_list), 5)
        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=True,
                     ctype='rpm',
                     repo='f17-updates-testing',
                     agent='bowlofeggs'),
            force=True)

        # Ensure our two updates were moved
        self.assertEqual(len(self.koji.__moved__), 2)
        self.assertEqual(len(self.koji.__added__), 0)

        # Ensure the most recent version is tagged last in order to be the 'koji latest-pkg'
        self.assertEqual(self.koji.__moved__[0],
                         (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-1.fc17'))
        self.assertEqual(self.koji.__moved__[1],
                         (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-2.fc17'))

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.mail._send_mail')
    def test_testing_digest(self, mail, *args):
        self.expected_sems = 1

        t = RPMComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)

        t.run()

        self.assertEqual(t.testing_digest[u'Fedora 17'][u'bodhi-2.0-1.fc17'], """\
================================================================================
 libseccomp-2.1.0-1.fc20 (FEDORA-%s-a3bbe1a8f2)
 Enhanced seccomp library
--------------------------------------------------------------------------------
Update Information:

Useful details!
--------------------------------------------------------------------------------
ChangeLog:

--------------------------------------------------------------------------------
References:

  [ 1 ] Bug #12345 - None
        https://bugzilla.redhat.com/show_bug.cgi?id=12345
  [ 2 ] CVE-1985-0110
        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-1985-0110
--------------------------------------------------------------------------------

""" % time.strftime('%Y'))

        mail.assert_called_with(config.get('bodhi_email'), config.get('fedora_test_announce_list'),
                                mock.ANY)
        assert len(mail.mock_calls) == 2, len(mail.mock_calls)
        body = mail.mock_calls[1][1][2]
        assert body.startswith(
            ('From: updates@fedoraproject.org\r\nTo: %s\r\nX-Bodhi: fedoraproject.org\r\nSubject: '
             'Fedora 17 updates-testing report\r\n\r\nThe following builds have been pushed to '
             'Fedora 17 updates-testing\n\n    bodhi-2.0-1.fc17\n\nDetails about builds:\n\n\n====='
             '===========================================================================\n '
             'libseccomp-2.1.0-1.fc20 (FEDORA-%s-a3bbe1a8f2)\n Enhanced seccomp library\n----------'
             '----------------------------------------------------------------------\nUpdate '
             'Information:\n\nUseful details!\n----------------------------------------------------'
             '----------------------------\nChangeLog:\n\n-----------------------------------------'
             '---------------------------------------\nReferences:\n\n  [ 1 ] Bug #12345 - None'
             '\n        https://bugzilla.redhat.com/show_bug.cgi?id=12345\n  [ 2 ] CVE-1985-0110'
             '\n        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-1985-0110\n----------'
             '----------------------------------------------------------------------\n\n') % (
                config.get('fedora_test_announce_list'), time.strftime('%Y'))), repr(body)

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_mash_invalid_dir(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = Compose.from_dict(session, msg['body']['msg']['composes'][0])
            t.release = session.query(Release).filter_by(name=u'F17').one()
            try:
                fake_popen = mock.MagicMock()
                fake_stdout = '''Some output
Some more output ...... This is not a Compose dir: ....
Compose dir: /tmp/nonsensical_directory
That was the actual one'''
                fake_popen.communicate = lambda: (fake_stdout, 'hello')
                fake_popen.poll.return_value = None
                fake_popen.returncode = 0
                t._startyear = datetime.datetime.utcnow().year
                t._wait_for_pungi(fake_popen)
                assert False, "Mash with invalid directory did not crash"
            except Exception as ex:
                expected_error = ('Directory at /tmp/nonsensical_directory does not look like a '
                                  'compose')
                expected_error = expected_error.format(datetime.datetime.utcnow().year)
                assert str(ex) == expected_error
            t.db = None

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_mash_no_found_dirs(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = Compose.from_dict(session, msg['body']['msg']['composes'][0])
            t.release = session.query(Release).filter_by(name=u'F17').one()
            try:
                fake_popen = mock.MagicMock()
                fake_stdout = '''Some output
    Some more output ...... This is not a Compose dir: ....
    That was the actual one'''
                fake_popen.communicate = lambda: (fake_stdout, 'hello')
                fake_popen.poll.return_value = None
                fake_popen.returncode = 0
                t._startyear = datetime.datetime.utcnow().year
                t._wait_for_pungi(fake_popen)
                assert False, "Mash without generated dirs did not crash"
            except Exception as ex:
                expected_error = ('Unable to find the path to the compose')
                expected_error = expected_error.format(datetime.datetime.utcnow().year)
                assert str(ex) == expected_error
            t.db = None

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_sanity_check_empty_dir(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t._wait_for_pungi(self._generate_fake_pungi(t, 'testing_tag', t.compose.release,
                                                        empty=True, noarches=True)())
            t.db = None

        # test without any arches
        assert 'completed_repo' in t._checkpoints
        try:
            t._sanity_check_repo()
            assert False, "Sanity check didn't fail with empty dir"
        except Exception as ex:
            assert '[Errno 2] No such file or directory' in str(ex)

        assert 'completed_repo' not in t._checkpoints
        save_state.assert_called()

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_sanity_check_no_arches(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t._wait_for_pungi(self._generate_fake_pungi(t, 'testing_tag', t.compose.release,
                                                        noarches=True)())
            t.db = None

        # test without any arches
        assert 'completed_repo' in t._checkpoints
        try:
            t._sanity_check_repo()
            assert False, "Sanity check didn't fail with archless compose"
        except Exception as ex:
            assert str(ex) == "Empty compose found"

        assert 'completed_repo' not in t._checkpoints
        save_state.assert_called()

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_sanity_check_valid(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t._wait_for_pungi(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
            t.db = None

        # test with valid repodata
        for arch in ('i386', 'x86_64', 'armhfp'):
            repo = os.path.join(t.path, 'compose', 'Everything', arch, 'os')
            mkmetadatadir(repo)
            os.makedirs(os.path.join(repo, 'Packages', 'a'))
            name = 'test.rpm'
            if arch == 'armhfp':
                name = 'test.notrpm'
            with open(os.path.join(repo, 'Packages', 'a', name), 'w') as tf:
                tf.write('foo')

        mkmetadatadir(os.path.join(t.path, 'compose', 'Everything', 'source', 'tree'))
        os.makedirs(os.path.join(t.path, 'compose', 'Everything', 'source', 'tree', 'Packages',
                                 'a'))
        with open(os.path.join(t.path, 'compose', 'Everything', 'source', 'tree', 'Packages', 'a',
                               'test.src.rpm'), 'w') as tf:
            tf.write('bar')

        assert 'completed_repo' in t._checkpoints
        save_state.reset_mock()
        t._sanity_check_repo()
        assert 'completed_repo' in t._checkpoints
        save_state.assert_not_called()

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_sanity_check_broken_repodata(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._startyear = datetime.datetime.utcnow().year
            t._checkpoints = {}
            t._wait_for_pungi(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
            t.db = None

        # test with valid repodata
        for arch in ('i386', 'x86_64', 'armhfp'):
            repo = os.path.join(t.path, 'compose', 'Everything', arch, 'os')
            mkmetadatadir(repo)

            # test with truncated/busted repodata
            xml = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata',
                               'repomd.xml')
            with open(xml) as f:
                repomd = f.read()
            with open(xml, 'w') as f:
                f.write(repomd[:-10])

        save_state.assert_called_once_with(ComposeState.punging)
        assert 'completed_repo' in t._checkpoints
        save_state.reset_mock()
        try:
            t._sanity_check_repo()
            assert False, 'Busted metadata passed'
        except exceptions.RepodataException:
            pass
        assert 'completed_repo' not in t._checkpoints
        save_state.assert_called()

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_sanity_check_symlink(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t._wait_for_pungi(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
            t.db = None

        # test with valid repodata
        for arch in ('i386', 'x86_64', 'armhfp'):
            repo = os.path.join(t.path, 'compose', 'Everything', arch, 'os')
            mkmetadatadir(repo)
            os.makedirs(os.path.join(repo, 'Packages', 'a'))
            os.symlink('/dev/null', os.path.join(repo, 'Packages', 'a', 'test.notrpm'))

        mkmetadatadir(os.path.join(t.path, 'compose', 'Everything', 'source', 'tree'))
        os.makedirs(os.path.join(t.path, 'compose', 'Everything', 'source', 'tree', 'Packages',
                                 'a'))
        os.symlink('/dev/null', os.path.join(t.path, 'compose', 'Everything', 'source', 'tree',
                                             'Packages', 'a', 'test.src.rpm'))

        assert 'completed_repo' in t._checkpoints
        save_state.reset_mock()
        try:
            t._sanity_check_repo()
            assert False, "Symlinks passed"
        except Exception as ex:
            assert str(ex) == "Symlinks found"
        assert 'completed_repo' not in t._checkpoints
        save_state.assert_called()

    @mock.patch('bodhi.server.consumers.masher.ComposerThread.save_state')
    def test_sanity_check_directories_missing(self, save_state):
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t._wait_for_pungi(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
            t.db = None

        # test with valid repodata
        for arch in ('i386', 'x86_64', 'armhfp'):
            repo = os.path.join(t.path, 'compose', 'Everything', arch, 'os')
            mkmetadatadir(repo)
            shutil.rmtree(os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'Packages'))

        mkmetadatadir(os.path.join(t.path, 'compose', 'Everything', 'source', 'tree'))

        assert 'completed_repo' in t._checkpoints
        save_state.reset_mock()
        try:
            t._sanity_check_repo()
            assert False, "Missing directories passed"
        except OSError as oex:
            assert oex.errno == errno.ENOENT
        assert 'completed_repo' not in t._checkpoints
        save_state.assert_called()

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_security_update_priority(self, publish, *args):
        self.expected_sems = 2

        with self.db_factory() as db:
            up = db.query(Update).one()
            user = db.query(User).first()

            # Create a security update for a different release
            release = Release(
                name=u'F18', long_name=u'Fedora 18',
                id_prefix=u'FEDORA', version=u'18',
                dist_tag=u'f18', stable_tag=u'f18-updates',
                testing_tag=u'f18-updates-testing',
                candidate_tag=u'f18-updates-candidate',
                pending_signing_tag=u'f18-updates-testing-signing',
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override',
                state=ReleaseState.current,
                branch=u'f18')
            db.add(release)
            build = RpmBuild(nvr=u'bodhi-2.0-1.fc18', release=release, package=up.builds[0].package,
                             signed=True)
            db.add(build)
            update = Update(
                title=u'bodhi-2.0-1.fc18',
                builds=[build], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release,
                test_gating_status=TestGatingStatus.passed)
            update.type = UpdateType.security
            db.add(update)

            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        self.masher.consume(self._make_msg())

        # Ensure that F18 runs before F17
        calls = publish.mock_calls
        # Order of fedmsgs at the the moment:
        # masher.start
        # mashing f18
        # complete.stable (for each update)
        # errata.publish
        # mashtask.complete
        # mashing f17
        # complete.testing
        # mashtask.complete
        self.assertEqual(calls[1], mock.call(
            force=True,
            msg={'repo': u'f18-updates',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc18'],
                 'agent': 'bowlofeggs'},
            topic='mashtask.mashing'))
        self.assertEqual(calls[4], mock.call(
            force=True,
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f18-updates',
                 'agent': 'bowlofeggs'},
            topic='mashtask.complete'))
        self.assertEqual(calls[5], mock.call(
            force=True,
            msg={'repo': u'f17-updates-testing',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc17'],
                 'agent': 'bowlofeggs'},
            topic='mashtask.mashing'))
        self.assertEqual(calls[-1], mock.call(
            force=True,
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f17-updates-testing',
                 'agent': 'bowlofeggs'},
            topic='mashtask.complete'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_security_update_priority_testing(self, publish, *args):
        self.expected_sems = 2

        with self.db_factory() as db:
            up = db.query(Update).one()
            up.type = UpdateType.security
            up.request = UpdateRequest.testing
            user = db.query(User).first()

            # Create a security update for a different release
            release = Release(
                name=u'F18', long_name=u'Fedora 18',
                id_prefix=u'FEDORA', version=u'18',
                dist_tag=u'f18', stable_tag=u'f18-updates',
                testing_tag=u'f18-updates-testing',
                candidate_tag=u'f18-updates-candidate',
                pending_signing_tag=u'f18-updates-testing-signing',
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override',
                state=ReleaseState.current,
                branch=u'f18')
            db.add(release)
            build = RpmBuild(nvr=u'bodhi-2.0-1.fc18', release=release, package=up.builds[0].package,
                             signed=True)
            db.add(build)
            update = Update(
                title=u'bodhi-2.0-1.fc18',
                builds=[build], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release,
                test_gating_status=TestGatingStatus.passed)
            update.type = UpdateType.enhancement
            db.add(update)

            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        self.masher.consume(self._make_msg())

        # Ensure that F17 updates-testing runs before F18
        calls = publish.mock_calls
        self.assertEqual(calls[1], mock.call(
            msg={'repo': u'f17-updates-testing',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc17'],
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.mashing'))
        self.assertEqual(calls[3], mock.call(
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f17-updates-testing',
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.complete'))
        self.assertEqual(calls[4], mock.call(
            msg={'repo': u'f18-updates',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc18'],
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.mashing'))
        self.assertEqual(calls[-1], mock.call(
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f18-updates',
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.complete'))

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_security_updates_parallel(self, publish, *args):
        self.expected_sems = 2

        with self.db_factory() as db:
            up = db.query(Update).one()
            up.type = UpdateType.security
            up.status = UpdateStatus.testing
            up.request = UpdateRequest.stable
            user = db.query(User).first()

            # Create a security update for a different release
            release = Release(
                name=u'F18', long_name=u'Fedora 18',
                id_prefix=u'FEDORA', version=u'18',
                dist_tag=u'f18', stable_tag=u'f18-updates',
                testing_tag=u'f18-updates-testing',
                candidate_tag=u'f18-updates-candidate',
                pending_signing_tag=u'f18-updates-testing-signing',
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override',
                state=ReleaseState.current,
                branch=u'f18')
            db.add(release)
            build = RpmBuild(nvr=u'bodhi-2.0-1.fc18', release=release, package=up.builds[0].package,
                             signed=True)
            db.add(build)
            update = Update(
                title=u'bodhi-2.0-1.fc18',
                builds=[build], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release,
                test_gating_status=TestGatingStatus.passed)
            update.type = UpdateType.security
            db.add(update)

            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        self.masher.consume(self._make_msg())

        # Ensure that F18 and F17 run in parallel
        calls = publish.mock_calls
        if calls[1] == mock.call(
                msg={'repo': u'f18-updates',
                     'ctype': 'rpm',
                     'updates': [u'bodhi-2.0-1.fc18'],
                     'agent': 'bowlofeggs'},
                force=True, topic='mashtask.mashing'):
            self.assertEqual(
                calls[2],
                mock.call(msg={'repo': u'f17-updates',
                               'ctype': 'rpm',
                               'updates': [u'bodhi-2.0-1.fc17'],
                               'agent': 'bowlofeggs'},
                          force=True, topic='mashtask.mashing'))
        elif calls[1] == self.assertEqual(
                calls[1],
                mock.call(
                    msg={'repo': u'f17-updates',
                         'ctype': 'rpm',
                         'updates': [u'bodhi-2.0-1.fc17'],
                         'agent': 'bowlofeggs'},
                    force=True, topic='mashtask.mashing')):
            self.assertEqual(
                calls[2],
                mock.call(msg={'repo': u'f18-updates',
                               'ctype': 'rpm',
                               'updates': [u'bodhi-2.0-1.fc18']},
                          force=True, topic='mashtask.mashing'))

    @mock.patch('bodhi.server.notifications.publish')
    def test_mash_invalid_ctype(self, publish, *args):
        msg = self._make_msg()
        msg['body']['msg']['composes'][0]['content_type'] = ContentType.base.value

        with mock.patch.object(self.masher, '_get_composes',
                               return_value=msg['body']['msg']['composes']):
            self.masher.log = mock.MagicMock()
            self.masher.work(msg)
            self.masher.log.error.assert_called_once_with(
                'Unsupported content type %s submitted for mashing. SKIPPING', 'base')

    def test_base_masher_pungi_not_implemented(self, *args):
        msg = self._make_msg()
        t = PungiComposerThread(self.semmock, msg['body']['msg']['composes'][0], 'ralph', log,
                                self.db_factory, self.tempdir)

        with self.assertRaises(NotImplementedError):
            t._copy_additional_pungi_files(None, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch.dict(
        config,
        {'pungi.cmd': '/usr/bin/false'})
    def test_mash_early_exit(self, publish, *args):
        self.expected_sems = 1

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)

        t.run()

        self.assertFalse(t.success)
        with self.db_factory() as db:
            compose = Compose.from_dict(db, msg['body']['msg']['composes'][0])
            self.assertEqual(compose.state, ComposeState.failed)
            self.assertEqual(compose.error_message, 'Pungi returned error, aborting!')
        self.assertEqual(t._checkpoints, {'determine_and_perform_tag_actions': True})

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_mash_late_exit(self, publish, *args):
        self.expected_sems = 1

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)

        with self.db_factory() as session:
            with tempfile.NamedTemporaryFile(delete=False) as script:
                script.write(b'#!/bin/bash\nsleep 5\nexit 1\n')
                script.close()
                os.chmod(script.name, 0o755)

                with mock.patch.dict(config, {'pungi.cmd': script.name}):
                    t.run()

            self.assertFalse(t.success)
            compose = Compose.from_dict(session, msg['body']['msg']['composes'][0])
            self.assertEqual(compose.state, ComposeState.failed)
            self.assertEqual(compose.error_message, 'Pungi exited with status 1')
        self.assertEqual(t._checkpoints, {'determine_and_perform_tag_actions': True})

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.scripts.clean_old_mashes.NUM_TO_KEEP', 2)
    @mock.patch('bodhi.server.notifications.publish')
    def test_mash(self, publish, *args):
        self.expected_sems = 1

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        mash_dir = os.path.join(self.tempdir, 'cool_dir')

        # Set up some directories that look similar to what might be found in production, with
        # some directories that don't match the pattern of ending in -<timestamp>.
        dirs = [
            'dist-5E-epel-161003.0724', 'dist-5E-epel-161011.0458', 'dist-5E-epel-161012.1854',
            'dist-5E-epel-161013.1711', 'dist-5E-epel-testing-161001.0424',
            'dist-5E-epel-testing-161003.0856', 'dist-5E-epel-testing-161006.0053',
            'dist-6E-epel-161002.2331', 'dist-6E-epel-161003.2046',
            'dist-6E-epel-testing-161001.0528', 'epel7-161003.0724', 'epel7-161003.2046',
            'epel7-161004.1423', 'epel7-161005.1122', 'epel7-testing-161001.0424',
            'epel7-testing-161003.0621', 'epel7-testing-161003.2217', 'f23-updates-161002.2331',
            'f23-updates-161003.1302', 'f23-updates-161004.1423', 'f23-updates-161005.0259',
            'f23-updates-testing-161001.0424', 'f23-updates-testing-161003.0621',
            'f23-updates-testing-161003.2217', 'f24-updates-161002.2331',
            'f24-updates-161003.1302', 'f24-updates-testing-161001.0424',
            'this_should_get_left_alone', 'f23-updates-should_be_untouched',
            'f23-updates.repocache', 'f23-updates-testing-blank']
        [os.makedirs(os.path.join(mash_dir, d)) for d in dirs]
        # Now let's make a few files here and there.
        with open(os.path.join(mash_dir, 'dist-5E-epel-161003.0724', 'oops.txt'), 'w') as oops:
            oops.write('This mash failed to get cleaned and left this file around, oops!')
        with open(os.path.join(mash_dir, 'COOL_FILE.txt'), 'w') as cool_file:
            cool_file.write('This file should be allowed to hang out here because it\'s cool.')

        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, mash_dir)

        with self.db_factory() as session:
            with mock.patch('bodhi.server.consumers.masher.subprocess.Popen') as Popen:
                with mock.patch.dict(config, {'mash_dir': mash_dir}):
                    release = session.query(Release).filter_by(name=u'F17').one()
                    Popen.side_effect = self._generate_fake_pungi(t, 'stable_tag', release)
                    t.run()

        # We expect these and only these directories to remain.
        expected_dirs = {
            'dist-5E-epel-161012.1854', 'dist-5E-epel-161013.1711',
            'dist-5E-epel-testing-161003.0856', 'dist-5E-epel-testing-161006.0053',
            'dist-6E-epel-161002.2331', 'dist-6E-epel-161003.2046',
            'dist-6E-epel-testing-161001.0528', 'epel7-161004.1423', 'epel7-161005.1122',
            'epel7-testing-161003.0621', 'epel7-testing-161003.2217', 'f23-updates-161004.1423',
            'f23-updates-161005.0259', 'f23-updates-testing-161003.0621',
            'f23-updates-testing-161003.2217', 'f24-updates-161002.2331',
            'f24-updates-161003.1302', 'f24-updates-testing-161001.0424',
            'this_should_get_left_alone', 'f23-updates-should_be_untouched',
            'f23-updates.repocache', 'f23-updates-testing-blank'}
        actual_dirs = set([
            d for d in os.listdir(mash_dir)
            if os.path.isdir(os.path.join(mash_dir, d)) and not d.startswith("Fedora-17-updates")])

        # Assert that remove_old_composes removes the correct items and leaves the rest in place.
        self.assertEqual(actual_dirs, expected_dirs)
        # The cool file should still be here
        actual_files = [f for f in os.listdir(mash_dir)
                        if os.path.isfile(os.path.join(mash_dir, f))]
        self.assertEqual(actual_files, ['COOL_FILE.txt'])

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            repo='f17-updates',
                                            ctype='rpm',
                                            agent='ralph'))
        publish.assert_any_call(topic='update.complete.stable',
                                force=True,
                                msg=mock.ANY)

        self.assertEqual(
            Popen.mock_calls,
            [mock.call(
                [config['pungi.cmd'], '--config', '{}/pungi.conf'.format(t._pungi_conf_dir),
                 '--quiet', '--print-output-dir', '--target-dir', t.mash_dir, '--old-composes',
                 t.mash_dir, '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                mash_dir, 'Fedora-17-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'compose_done': True,
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})
        self.assertTrue(os.path.exists(mash_dir))

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_mash_module(self, publish, *args):
        self.expected_sems = 1

        with self.db_factory() as db:
            user = db.query(User).first()

            release = self.create_release('27M')
            package = Package(name=u'testmodule',
                              type=ContentType.module)
            db.add(package)
            build1 = ModuleBuild(nvr=u'testmodule-master-20171.1',
                                 release=release, signed=True,
                                 package=package)
            db.add(build1)
            build2 = ModuleBuild(nvr=u'testmodule-master-20172.2',
                                 release=release, signed=True,
                                 package=package)
            db.add(build2)
            update = Update(
                title=u'testmodule-master-20172.2',
                builds=[build2], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release,
                test_gating_status=TestGatingStatus.passed)
            update.type = UpdateType.security
            db.add(update)

            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        msg = self._make_msg(['--releases', 'F27M'])
        t = ModuleComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                 'puiterwijk', log, self.db_factory, self.tempdir)

        with self.db_factory() as session:
            with mock.patch('bodhi.server.consumers.masher.subprocess.Popen') as Popen:
                release = session.query(Release).filter_by(name=u'F27M').one()
                Popen.side_effect = self._generate_fake_pungi(t, 'stable_tag', release)
                t.run()

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            repo='f27M-updates',
                                            ctype='module',
                                            agent='puiterwijk'))
        publish.assert_any_call(topic='update.complete.stable',
                                force=True,
                                msg=mock.ANY)

        self.assertEqual(t._module_defs, [{'context': '2',
                                           'version': '20172',
                                           'name': 'testmodule',
                                           'stream': 'master'}])
        self.assertEqual(t._module_list, ['testmodule:master:20172'])

        EXPECTED_VARIANTS = '''Raw NSVs:
testmodule:master:20172

Calculated NSVCs:
testmodule:master:20172:2
'''
        self.assertEqual(t._variants_file, EXPECTED_VARIANTS)

        self.assertEqual(
            Popen.mock_calls,
            [mock.call(
                [config['pungi.cmd'], '--config', '{}/pungi.conf'.format(t._pungi_conf_dir),
                 '--quiet', '--print-output-dir', '--target-dir', t.mash_dir, '--old-composes',
                 t.mash_dir, '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                self.tempdir,
                'Fedora-27-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'compose_done': True,
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})

    def test_mash_module_koji_multicall_result_empty_list(self):
        release = self.create_release('27M')
        package = Package(name=u'testmodule',
                          type=ContentType.module)
        build = ModuleBuild(nvr=u'testmodule-master-20171',
                            release=release, signed=True,
                            package=package)
        t = ModuleComposerThread(self.semmock, {}, 'puiterwijk', log, self.db_factory,
                                 self.tempdir)
        with self.assertRaises(Exception) as exc:
            t._raise_on_get_build_multicall_error([], build)

        self.assertEqual(
            six.text_type(exc.exception),
            'Empty list returned for getBuild("%s").' % (build.nvr))

    def test_mash_module_koji_multicall_result_dict(self):
        release = self.create_release('27M')
        package = Package(name=u'testmodule',
                          type=ContentType.module)
        build = ModuleBuild(nvr=u'testmodule-master-20171',
                            release=release, signed=True,
                            package=package)
        t = ModuleComposerThread(self.semmock, {}, 'puiterwijk', log, self.db_factory,
                                 self.tempdir)
        with self.assertRaises(Exception) as exc:
            t._raise_on_get_build_multicall_error({}, build)

        self.assertEqual(
            six.text_type(exc.exception),
            'Unexpected data returned for getBuild("%s"): {}.' % (build.nvr))

    @mock.patch(**mock_failed_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_failed_gating(self, publish, *args):
        self.expected_sems = 1

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMComposerThread(
            self.semmock, msg['body']['msg']['composes'][0], 'ralph', log, self.db_factory,
            self.tempdir)

        with self.db_factory() as session:
            with mock.patch('bodhi.server.consumers.masher.subprocess.Popen') as Popen:
                release = session.query(Release).filter_by(name=u'F17').one()
                Popen.side_effect = self._generate_fake_pungi(t, 'stable_tag', release)
                t.run()

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            ctype='rpm',
                                            repo='f17-updates',
                                            agent='ralph'))
        publish.assert_any_call(topic='update.eject', msg=mock.ANY, force=True)

        self.assertEqual(
            Popen.mock_calls,
            [mock.call(
                [config['pungi.cmd'], '--config', '{}/pungi.conf'.format(t._pungi_conf_dir),
                 '--quiet', '--print-output-dir', '--target-dir', t.mash_dir, '--old-composes',
                 t.mash_dir, '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                self.tempdir, 'Fedora-17-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'compose_done': True,
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})

    @mock.patch.dict(config, {'test_gating.required': True})
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.consumers.masher.time.sleep', return_value=None)
    @mock.patch('bodhi.server.notifications.publish')
    def test_test_gating_status_failed(self, publish, *args):
        """If the update's test_gating_status is failed it should be ejected."""
        self.expected_sems = 1
        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        u = Update.query.filter_by(title='bodhi-2.0-1.fc17').one()
        u.test_gating_status = TestGatingStatus.failed
        u.requirements = ''
        msg = self._make_msg()
        t = RPMComposerThread(
            self.semmock, msg['body']['msg']['composes'][0], 'ralph', log, self.db_factory,
            self.tempdir)

        with self.db_factory() as session:
            with mock.patch('bodhi.server.consumers.masher.subprocess.Popen') as Popen:
                release = session.query(Release).filter_by(name=u'F17').one()
                Popen.side_effect = self._generate_fake_pungi(t, 'stable_tag', release)
                t.run()

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            ctype='rpm',
                                            repo='f17-updates',
                                            agent='ralph'))
        publish.assert_any_call(topic='update.eject', msg=mock.ANY, force=True)
        u = Update.query.filter_by(title='bodhi-2.0-1.fc17').one()
        self.assertEqual(
            u.comments[-1].text,
            ("bodhi-2.0-1.fc17 ejected from the push because 'Required tests did not pass on this "
             "update'"))
        # The request got sent back to None since it was ejected.
        self.assertEqual(u.request, None)
        self.assertEqual(u.status, UpdateStatus.pending)

    @mock.patch.dict(config, {'test_gating.required': True})
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.consumers.masher.time.sleep', return_value=None)
    @mock.patch('bodhi.server.notifications.publish')
    def test_test_gating_status_passed(self, publish, *args):
        """If the update's test_gating_status is passed it should not be ejected."""
        self.expected_sems = 1
        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        u = Update.query.filter_by(title='bodhi-2.0-1.fc17').one()
        u.test_gating_status = TestGatingStatus.passed
        u.requirements = ''
        msg = self._make_msg()
        t = RPMComposerThread(
            self.semmock, msg['body']['msg']['composes'][0], 'ralph', log, self.db_factory,
            self.tempdir)

        with self.db_factory() as session:
            with mock.patch('bodhi.server.consumers.masher.subprocess.Popen') as Popen:
                release = session.query(Release).filter_by(name=u'F17').one()
                Popen.side_effect = self._generate_fake_pungi(t, 'stable_tag', release)
                t.run()

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            ctype='rpm',
                                            repo='f17-updates',
                                            agent='ralph'))
        topics = {c[2]['topic'] for c in publish.mock_calls}
        self.assertNotIn('update.eject', topics)
        u = Update.query.filter_by(title='bodhi-2.0-1.fc17').one()
        self.assertEqual(u.comments[-1].text, 'This update has been pushed to stable.')
        # The update should be stable.
        self.assertEqual(u.request, None)
        self.assertEqual(u.status, UpdateStatus.stable)

    @mock.patch(**mock_absent_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_absent_gating(self, publish, *args):
        # Set the request to stable right out the gate so we can test gating
        self.expected_sems = 1

        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()

        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0], 'ralph', log,
                              self.db_factory, self.tempdir)

        with self.db_factory() as session:
            with mock.patch('bodhi.server.consumers.masher.subprocess.Popen') as Popen:
                release = session.query(Release).filter_by(name=u'F17').one()
                Popen.side_effect = self._generate_fake_pungi(t, 'stable_tag', release)
                t.run()

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            ctype='rpm',
                                            repo='f17-updates',
                                            agent='ralph'))
        publish.assert_any_call(topic='update.eject', msg=mock.ANY, force=True)

        self.assertEqual(
            Popen.mock_calls,
            [mock.call(
                [config['pungi.cmd'], '--config', '{}/pungi.conf'.format(t._pungi_conf_dir),
                 '--quiet', '--print-output-dir', '--target-dir', t.mash_dir, '--old-composes',
                 t.mash_dir, '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                self.tempdir, 'Fedora-17-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'compose_done': True,
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})

    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    @mock.patch('bodhi.server.bugs.bugtracker.modified')
    @mock.patch('bodhi.server.bugs.bugtracker.on_qa')
    def test_modify_testing_bugs(self, on_qa, modified, *args):
        self.expected_sems = 1

        self.masher.consume(self._make_msg())

        expected_message = (
            u'bodhi-2.0-1.fc17 has been pushed to the Fedora 17 testing repository. If problems '
            u'still persist, please make note of it in this bug report.\nSee '
            u'https://fedoraproject.org/wiki/QA:Updates_Testing for\ninstructions on how to '
            u'install test updates.\nYou can provide feedback for this update here: {}')
        expected_message = expected_message.format(
            urlparse.urljoin(
                config['base_address'],
                '/updates/FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.now().year)))
        on_qa.assert_called_once_with(12345, expected_message)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.bugs.bugtracker.comment')
    @mock.patch('bodhi.server.bugs.bugtracker.close')
    def test_modify_stable_bugs(self, close, comment, *args):
        self.expected_sems = 1

        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()

        t = RPMComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                              'ralph', log, self.db_factory, self.tempdir)

        t.run()

        close.assert_called_with(
            12345,
            versions=dict(bodhi=u'bodhi-2.0-1.fc17'),
            comment=(u'bodhi-2.0-1.fc17 has been pushed to the Fedora 17 stable repository. If '
                     u'problems still persist, please make note of it in this bug report.'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_status_comment_testing(self, *args):
        self.expected_sems = 1

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEqual(len(up.comments), 2)

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEqual(len(up.comments), 3)
            self.assertEqual(up.comments[-1]['text'], u'This update has been pushed to testing.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_status_comment_stable(self, *args):
        self.expected_sems = 1

        with self.db_factory() as session:
            up = session.query(Update).one()
            up.request = UpdateRequest.stable
            self.assertEqual(len(up.comments), 2)

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEqual(len(up.comments), 3)
            self.assertEqual(up.comments[-1]['text'], u'This update has been pushed to stable.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_get_security_updates(self, *args):
        msg = self._make_msg()
        t = ComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                           'ralph', log, self.db_factory, self.tempdir)
        with self.db_factory() as session:
            t.db = session
            u = session.query(Update).one()
            u.type = UpdateType.security
            u.status = UpdateStatus.testing
            u.request = None
            session.commit()
            release = session.query(Release).one()

            updates = t.get_security_updates(release.long_name)

            self.assertEqual(len(updates), 1)
            self.assertEqual(updates[0].title, u.builds[0].nvr)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_unlock_updates(self, *args):
        self.expected_sems = 1

        with self.db_factory() as session:
            up = session.query(Update).one()
            up.request = UpdateRequest.stable
            self.assertEqual(len(up.comments), 2)

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEqual(up.locked, False)
            self.assertEqual(up.status, UpdateStatus.stable)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_resume_push(self, *args):
        self.expected_sems = 2

        with mock.patch.object(ComposerThread, 'generate_testing_digest', mock_exc):
            with self.db_factory() as session:
                up = session.query(Update).one()
                up.request = UpdateRequest.testing
                up.status = UpdateStatus.pending

            # Simulate a failed push
            self.masher.consume(self._make_msg())

        # Ensure that the update hasn't changed state
        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEqual(up.request, UpdateRequest.testing)
            self.assertEqual(up.status, UpdateStatus.pending)

        # Resume the push
        msg = self._make_msg()
        msg['body']['msg']['resume'] = True
        self.masher.consume(msg)

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEqual(up.status, UpdateStatus.testing)
            self.assertEqual(up.request, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_retry_done_compose(self, mock_cmd, mock_publish,
                                mock_wait_for_sync, mock_generate_updateinfo,
                                mock_wait_for_repo_signature, mock_stage_repo,
                                mock_sanity_check_repo, mock_wait_for_pungi,
                                mock_taskotron_results):
        self.expected_sems = 2

        # Crash during wait_for_sync. The compose itself is done.
        mock_wait_for_sync.side_effect = Exception
        with self.db_factory() as session:
            up = session.query(Update).one()
            up.request = UpdateRequest.testing
            up.status = UpdateStatus.pending

        # Simulate a failed push
        self.masher.consume(self._make_msg())

        # Assert that things were run
        mock_wait_for_pungi.assert_called()
        mock_sanity_check_repo.assert_called()
        mock_stage_repo.assert_called()
        mock_wait_for_repo_signature.assert_called()
        mock_generate_updateinfo.assert_called()
        mock_wait_for_sync.assert_called()

        # Reset mocks
        mock_wait_for_sync.side_effect = None
        mock_wait_for_pungi.reset_mock()
        mock_sanity_check_repo.reset_mock()
        mock_stage_repo.reset_mock()
        mock_wait_for_repo_signature.reset_mock()
        mock_generate_updateinfo.reset_mock()
        mock_wait_for_sync.reset_mock()

        # Resume the push
        msg = self._make_msg()
        msg['body']['msg']['resume'] = True
        self.masher.consume(msg)

        # Assert we did not actually recompose
        mock_wait_for_pungi.assert_not_called()
        mock_sanity_check_repo.assert_not_called()
        mock_stage_repo.assert_not_called()
        mock_wait_for_repo_signature.assert_not_called()
        mock_generate_updateinfo.assert_not_called()

        # Assert that we did wait for resync
        mock_wait_for_sync.assert_called()

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_stable_requirements_met_during_push(self, *args):
        """
        Test reaching the stablekarma threshold while the update is being
        pushed to testing
        """
        self.expected_sems = 2

        # Simulate a failed push
        with mock.patch.object(ComposerThread, 'determine_and_perform_tag_actions', mock_exc):
            with self.db_factory() as session:
                up = session.query(Update).one()
                up.request = UpdateRequest.testing
                up.status = UpdateStatus.pending
                self.assertEqual(up.stable_karma, 3)
            self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()

            # Ensure the update is still locked and in testing
            self.assertEqual(up.locked, True)
            self.assertEqual(up.status, UpdateStatus.pending)
            self.assertEqual(up.request, UpdateRequest.testing)

            # Have the update reach the stable karma threshold
            self.assertEqual(up.karma, 1)
            up.comment(session, u"foo", 1, u'foo')
            self.assertEqual(up.karma, 2)
            self.assertEqual(up.request, UpdateRequest.testing)
            up.comment(session, u"foo", 1, u'bar')
            self.assertEqual(up.karma, 3)
            self.assertEqual(up.request, UpdateRequest.testing)
            up.comment(session, u"foo", 1, u'biz')
            self.assertEqual(up.request, UpdateRequest.testing)
            self.assertEqual(up.karma, 4)

        # finish push and unlock updates
        msg = self._make_msg()
        msg['body']['msg']['resume'] = True
        self.masher.consume(msg)

        with self.db_factory() as session:
            up = session.query(Update).one()
            up.comment(session, u"foo", 1, u'baz')
            self.assertEqual(up.karma, 5)

            # Ensure the masher set the autokarma once the push is done
            self.assertEqual(up.locked, False)
            self.assertEqual(up.request, UpdateRequest.batched)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_timestamps(self, publish, *args):
        self.expected_sems = 2

        with self.db_factory() as session:
            release = session.query(Update).one().release
            pending_testing_tag = release.pending_testing_tag
            self.koji.__tagged__[session.query(Update).first().title] = [release.override_tag,
                                                                         pending_testing_tag]

        # Start the push
        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            # Set the update request to stable and the release to pending
            up = session.query(Update).one()
            self.assertIsNotNone(up.date_testing)
            self.assertIsNone(up.date_stable)
            up.request = UpdateRequest.stable

        # Ensure that fedmsg was called 3 times
        self.assertEqual(len(publish.call_args_list), 4)
        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            force=True,
            msg=dict(success=True,
                     repo='f17-updates-testing',
                     ctype='rpm',
                     agent='bowlofeggs'))

        self.koji.clear()

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            # Check that the request_complete method got run
            up = session.query(Update).one()
            self.assertIsNone(up.request)
            self.assertIsNotNone(up.date_stable)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsolete_older_updates(self, publish, *args):
        self.expected_sems = 1
        otherbuild = u'bodhi-2.0-2.fc17'

        with self.db_factory() as session:
            # Put the older update into testing
            oldupdate = session.query(Update).one()
            oldbuild = oldupdate.builds[0].nvr
            oldupdate.status = UpdateStatus.testing
            oldupdate.request = None
            oldupdate.locked = False

            # Create a newer build
            build = RpmBuild(nvr=otherbuild, package=oldupdate.builds[0].package, signed=True)
            session.add(build)
            update = Update(
                title=otherbuild, builds=[build], type=UpdateType.bugfix,
                request=UpdateRequest.testing, notes=u'second update', user=oldupdate.user)
            update.release = oldupdate.release
            session.add(update)
            session.flush()

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            # Ensure that the older update got obsoleted
            up = session.query(Update).filter_by(title=oldbuild).one()
            self.assertEqual(up.status, UpdateStatus.obsolete)
            self.assertEqual(up.request, None)

            # The latest update should be in testing
            up = session.query(Update).filter_by(title=otherbuild).one()
            self.assertEqual(up.status, UpdateStatus.testing)
            self.assertEqual(up.request, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_pungi')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_repo_signature')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread._wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.log.exception')
    @mock.patch('bodhi.server.models.BuildrootOverride.expire', side_effect=Exception())
    def test_expire_buildroot_overrides_exception(self, expire, exception_log, publish, *args):
        self.expected_sems = 1

        with self.db_factory() as db:
            release = db.query(Update).one().release
            pending_testing_tag = release.pending_testing_tag
            self.koji.__tagged__[db.query(Update).first().title] = [release.override_tag,
                                                                    pending_testing_tag]
            up = db.query(Update).one()
            up.release.state = ReleaseState.pending
            up.request = UpdateRequest.stable
        msg = self._make_msg()

        self.masher.consume(msg)

        exception_log.assert_called_once_with("Problem expiring override")


class ComposerThreadBaseTestCase(base.BaseTestCase):
    """Methods that are useful for testing ComposerThread subclasses."""

    def setUp(self):
        """
        Set up the test conditions.
        """
        super(ComposerThreadBaseTestCase, self).setUp()
        buildsys.setup_buildsystem({'buildsystem': 'dev'})
        self.tempdir = tempfile.mkdtemp()
        self.semmock = mock.MagicMock()

    def tearDown(self):
        """
        Clean up after the tests.
        """
        super(ComposerThreadBaseTestCase, self).tearDown()
        shutil.rmtree(self.tempdir)
        buildsys.teardown_buildsystem()

    def assert_sems(self, nr_expected):
        if nr_expected == 0:
            self.semmock.acquire.assert_not_called()
            self.semmock.release.assert_not_called()
        else:
            self.semmock.acquire.assert_called()
            self.semmock.release.assert_called()

        assert self.semmock.acquire.call_count == nr_expected
        assert self.semmock.acquire.call_count == self.semmock.release.call_count

    def _make_msg(self, extra_push_args=None):
        """
        Use bodhi-push to start a compose, and return the fedmsg that bodhi-push sends.

        Returns:
            dict: A dictionary of the fedmsg that bodhi-push sends.
        """
        return _make_msg(base.TransactionalSessionMaker(self.Session), extra_push_args)


class TestContainerComposerThread__compose_updates(ComposerThreadBaseTestCase):
    """Test ContainerComposerThread._compose_update()."""

    def setUp(self):
        super(TestContainerComposerThread__compose_updates, self).setUp()

        user = self.db.query(User).first()
        release = self.create_release('28C')
        release.branch = 'f28'
        package1 = Package(name=u'testcontainer1',
                           type=ContentType.container)
        self.db.add(package1)
        package2 = Package(name=u'testcontainer2',
                           type=ContentType.container)
        self.db.add(package2)
        build1 = ContainerBuild(nvr=u'testcontainer1-2.0.1-71.fc28', release=release, signed=True,
                                package=package1)
        self.db.add(build1)
        build2 = ContainerBuild(nvr=u'testcontainer2-1.0.1-1.fc28', release=release, signed=True,
                                package=package2)
        self.db.add(build2)
        update = Update(
            title=u'testcontainer1-2.0.1-71.fc28, testcontainer2-1.0.1-1.fc28',
            builds=[build1, build2], user=user,
            status=UpdateStatus.pending,
            request=UpdateRequest.testing,
            notes=u'Neat I can compose containers now', release=release,
            test_gating_status=TestGatingStatus.passed)
        update.type = UpdateType.bugfix
        self.db.add(update)
        # Wipe out the tag cache so it picks up our new release
        Release._tag_cache = None
        self.db.flush()

    @mock.patch('bodhi.server.consumers.masher.subprocess.Popen')
    def test_request_not_stable(self, Popen):
        """Ensure that the correct destination tag is used for non-stable updates."""
        Popen.return_value.communicate.return_value = ('out', 'err')
        Popen.return_value.returncode = 0
        msg = self._make_msg(['--releases', 'F28C'])
        t = ContainerComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                    'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        t._compose_updates()

        # Popen should have been called three times per build, once for each of the destination
        # tags. With two builds that is a total of 6 calls to Popen.
        expected_mock_calls = []
        for source in ('testcontainer1:2.0.1-71.fc28', 'testcontainer2:1.0.1-1.fc28'):
            for dtag in [source.split(':')[1], source.split(':')[1].split('-')[0], 'testing']:
                mock_call = mock.call(
                    [config['skopeo.cmd'], 'copy',
                     'docker://{}/f28/{}'.format(config['container.source_registry'], source),
                     'docker://{}/f28/{}:{}'.format(config['container.destination_registry'],
                                                    source.split(':')[0], dtag)],
                    shell=False, stderr=-1, stdout=-1, cwd=None)
                expected_mock_calls.append(mock_call)
                expected_mock_calls.append(mock.call().communicate())
        self.assertEqual(Popen.mock_calls, expected_mock_calls)

    @mock.patch('bodhi.server.consumers.masher.subprocess.Popen')
    def test_request_stable(self, Popen):
        """Ensure that the correct destination tag is used for stable updates."""
        Popen.return_value.communicate.return_value = ('out', 'err')
        Popen.return_value.returncode = 0
        ContainerBuild.query.first().update.request = UpdateRequest.stable
        msg = self._make_msg(['--releases', 'F28C'])
        t = ContainerComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                    'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        t._compose_updates()

        # Popen should have been called three times per build, once for each of the destination
        # tags. With two builds that is a total of 6 calls to Popen.
        expected_mock_calls = []
        for source in ('testcontainer1:2.0.1-71.fc28', 'testcontainer2:1.0.1-1.fc28'):
            for dtag in [source.split(':')[1], source.split(':')[1].split('-')[0], 'latest']:
                mock_call = mock.call(
                    [config['skopeo.cmd'], 'copy',
                     'docker://{}/f28/{}'.format(config['container.source_registry'], source),
                     'docker://{}/f28/{}:{}'.format(config['container.destination_registry'],
                                                    source.split(':')[0], dtag)],
                    shell=False, stderr=-1, stdout=-1, cwd=None)
                expected_mock_calls.append(mock_call)
                expected_mock_calls.append(mock.call().communicate())
        self.assertEqual(Popen.mock_calls, expected_mock_calls)

    @mock.patch('bodhi.server.consumers.masher.subprocess.Popen')
    def test_skopeo_error_code(self, Popen):
        """Assert that a RuntimeError is raised if skopeo returns a non-0 exit code."""
        Popen.return_value.communicate.return_value = ('out', 'err')
        Popen.return_value.returncode = 1
        ContainerBuild.query.first().update.request = UpdateRequest.stable
        msg = self._make_msg(['--releases', 'F28C'])
        t = ContainerComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                    'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        with self.assertRaises(RuntimeError) as exc:
            t._compose_updates()

        # Popen should have been called once.
        skopeo_cmd = [
            config['skopeo.cmd'], 'copy',
            'docker://{}/f28/testcontainer1:2.0.1-71.fc28'.format(
                config['container.source_registry']),
            'docker://{}/f28/testcontainer1:2.0.1-71.fc28'.format(
                config['container.destination_registry'])]
        Popen.assert_called_once_with(skopeo_cmd, shell=False, stderr=-1, stdout=-1, cwd=None)
        self.assertEqual(str(exc.exception),
                         '{} returned a non-0 exit code: 1'.format(' '.join(skopeo_cmd)))

    @mock.patch.dict(config, {'skopeo.extra_copy_flags': '--dest-tls-verify=false'})
    @mock.patch('bodhi.server.consumers.masher.subprocess.Popen')
    def test_skopeo_extra_copy_flags(self, Popen):
        """Test the skopeo.extra_copy_flags setting."""
        Popen.return_value.communicate.return_value = ('out', 'err')
        Popen.return_value.returncode = 0
        msg = self._make_msg(['--releases', 'F28C'])
        t = ContainerComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                    'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        t._compose_updates()

        # Popen should have been called three times per build, once for each of the destination
        # tags. With two builds that is a total of 6 calls to Popen.
        expected_mock_calls = []
        for source in ('testcontainer1:2.0.1-71.fc28', 'testcontainer2:1.0.1-1.fc28'):
            for dtag in [source.split(':')[1], source.split(':')[1].split('-')[0], 'testing']:
                mock_call = mock.call(
                    [config['skopeo.cmd'], 'copy', '--dest-tls-verify=false',
                     'docker://{}/f28/{}'.format(config['container.source_registry'], source),
                     'docker://{}/f28/{}:{}'.format(config['container.destination_registry'],
                                                    source.split(':')[0], dtag)],
                    shell=False, stderr=-1, stdout=-1, cwd=None)
                expected_mock_calls.append(mock_call)
                expected_mock_calls.append(mock.call().communicate())
        self.assertEqual(Popen.mock_calls, expected_mock_calls)


class TestPungiComposerThread__compose_updates(ComposerThreadBaseTestCase):
    """This class contains tests for the PungiComposerThread._compose_updates() method."""

    def test_mash_dir_dne(self):
        """If mash_dir does not exist, the method should create it."""
        msg = self._make_msg()
        mash_dir = os.path.join(self.tempdir, 'mash_dir')
        t = PungiComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, mash_dir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.skip_compose = True

        t._compose_updates()

        self.assertTrue(os.path.exists(mash_dir))


class TestPungiComposerThread__get_master_repomd_url(ComposerThreadBaseTestCase):
    """This class contains tests for the PungiComposerThread._get_master_repomd_url() method."""
    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_17_primary_arches': 'armhfp x86_64',
         'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml',
         'fedora_testing_alt_master_repomd':
         'http://example.com/pub/fedora-secondary/updates/testing/%s/%s/repodata.repomd.xml'})
    def test_alternative_arch(self):
        """
        Assert that the *_alt_master_repomd settings are used when the release does define primary
        arches and the arch being looked up is not in the primary arch list.
        """
        msg = self._make_msg()
        t = PungiComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        url = t._get_master_repomd_url('aarch64')

        self.assertEqual(
            url,
            'http://example.com/pub/fedora-secondary/updates/testing/17/aarch64/repodata.repomd.xml'
        )

        self.assert_sems(0)

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_17_primary_arches': 'armhfp x86_64',
         'fedora_testing_master_repomd': None,
         'fedora_testing_alt_master_repomd': None})
    def test_master_repomd_undefined(self):
        """
        Assert that a ValueError is raised when the config is missing a master_repomd config for
        the release.
        """
        msg = self._make_msg()

        t = PungiComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        with self.assertRaises(ValueError) as exc:
            t._get_master_repomd_url('aarch64')

        self.assertEqual(six.text_type(exc.exception),
                         'Could not find any of fedora_17_testing_alt_master_repomd,'
                         'fedora_testing_alt_master_repomd in the config file')

        self.assert_sems(0)

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_17_primary_arches': 'armhfp x86_64',
         'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml',
         'fedora_testing_alt_master_repomd':
         'http://example.com/pub/fedora-secondary/updates/testing/%s/%s/repodata.repomd.xml'})
    def test_primary_arch(self):
        """
        Assert that the *_master_repomd settings are used when the release does define primary
        arches and the arch being looked up is primary.
        """
        msg = self._make_msg()

        t = PungiComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        url = t._get_master_repomd_url('x86_64')

        self.assertEqual(
            url,
            'http://example.com/pub/fedora/linux/updates/testing/17/x86_64/repodata.repomd.xml'
        )

        self.assert_sems(0)

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_17_primary_arches': 'armhfp x86_64',
         'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml',
         'fedora_testing_alt_master_repomd':
         'http://example.com/pub/fedora-secondary/updates/testing/%s/%s/repodata.repomd.xml',
         'fedora_17_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/Everything/'
            '%s/repodata.repomd.xml'})
    def test_primary_arch_version_override(self):
        """
        Assert that if a release_version_request setting exists, that overrides release_request.
        """
        msg = self._make_msg()

        t = PungiComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        url = t._get_master_repomd_url('x86_64')

        self.assertEqual(
            url,
            'http://example.com/pub/fedora/linux/updates/testing/17/Everything/'
            'x86_64/repodata.repomd.xml'
        )

        self.assert_sems(0)

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml',
         'fedora_testing_alt_master_repomd':
         'http://example.com/pub/fedora-secondary/updates/testing/%s/%s/repodata.repomd.xml'})
    def test_primary_arches_undefined(self):
        """
        Assert that the *_master_repomd settings are used when the release does not have primary
        arches defined in the config file.
        """
        msg = self._make_msg()
        t = PungiComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        url = t._get_master_repomd_url('aarch64')

        self.assertEqual(
            url,
            'http://example.com/pub/fedora/linux/updates/testing/17/aarch64/repodata.repomd.xml'
        )

        self.assert_sems(0)


class TestComposerThread_perform_gating(ComposerThreadBaseTestCase):
    """Test the ComposerThread.perform_gating() method."""

    def test_expires_compose_updates(self):
        """Ensure that the method expires the compose's updates attribute."""
        msg = self._make_msg()
        t = ComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.compose.updates[0].test_gating_status = TestGatingStatus.failed
        t.db = self.db
        t.id = getattr(self.db.query(Release).one(), '{}_tag'.format('stable'))

        t.perform_gating()

        # Without the call to self.db.expire() at the end of perform_gating(), there would be 1
        # update here.
        self.assertEqual(len(t.compose.updates), 0)


class TestComposerThread__perform_tag_actions(ComposerThreadBaseTestCase):
    """This test class contains tests for the ComposerThread._perform_tag_actions() method."""
    @mock.patch('bodhi.server.consumers.masher.buildsys.wait_for_tasks')
    def test_with_failed_tasks(self, wait_for_tasks):
        """
        Assert that the method raises an Exception when the buildsys gives us failed tasks.
        """
        wait_for_tasks.return_value = ['failed_task_1']
        msg = self._make_msg()
        t = ComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.move_tags_async.append(
            (u'f26-updates-candidate', u'f26-updates-testing', u'bodhi-2.3.2-1.fc26'))

        with self.assertRaises(Exception) as exc:
            t._perform_tag_actions()

        self.assertEqual(six.text_type(exc.exception), "Failed to move builds: ['failed_task_1']")
        # Since the task didn't really fail (we just mocked that it did) the DevBuildsys should have
        # registered that the move occurred.
        self.assertEqual(buildsys.DevBuildsys.__moved__,
                         [('f26-updates-candidate', 'f26-updates-testing', 'bodhi-2.3.2-1.fc26')])

        self.assert_sems(0)


class TestComposerThread_remove_pending_tags(ComposerThreadBaseTestCase):
    """This test class contains tests for the ComposerThread.remove_pending_tags() method."""
    @mock.patch('bodhi.server.models.Update.remove_tag')
    def test_with_request_testing(self, remove_tag):
        """
        Assert that the method calls Update.remove_tag() twice for the pending_signing_tag
        and pending_testing_tag.
        """
        msg = self._make_msg()
        t = ComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.log.debug = mock.MagicMock()

        t.remove_pending_tags()

        self.assertEqual(remove_tag.call_count, 2)
        t.log.debug.assert_called_with("remove_pending_tags koji.multiCall result = %r", [])


class TestComposerThread_check_all_karma_thresholds(ComposerThreadBaseTestCase):
    """Test the ComposerThread.check_all_karma_thresholds() method."""
    @mock.patch('bodhi.server.models.Update.check_karma_thresholds',
                mock.MagicMock(side_effect=exceptions.BodhiException('BOOM')))
    def test_BodhiException(self):
        """Assert that a raised BodhiException gets caught and logged."""
        msg = self._make_msg()
        t = ComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.db = self.db
        t.log.exception = mock.MagicMock()

        t.check_all_karma_thresholds()

        t.log.exception.assert_called_once_with('Problem checking karma thresholds')

        self.assert_sems(0)


class TestComposerThread__determine_tag_actions(ComposerThreadBaseTestCase):
    """Test ComposerThread._determine_tag_actions()."""

    @mock.patch('bodhi.server.models.buildsys.get_session')
    @mock.patch('bodhi.server.notifications.publish')
    def test_from_tag_not_found(self, publish, get_session):
        """Updates should be ejected if the from tag cannot be determined."""
        tags = ['some', 'unknown', 'tags']
        get_session.return_value.listTags.return_value = [{'name': n} for n in tags]
        msg = self._make_msg()
        t = ComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.db = self.db
        t.id = getattr(self.db.query(Release).one(), '{}_tag'.format('stable'))
        t.skip_compose = True

        t._determine_tag_actions()

        # Since the update should have been ejected, no tags should get added to add_tags or
        # move_tags.
        for attr in ('add_tags_sync', 'move_tags_sync', 'add_tags_async', 'move_tags_async'):
            self.assertEqual(getattr(t, attr), [])
        up = self.db.query(Update).one()
        expected_reason = "Cannot find relevant tag for bodhi-2.0-1.fc17.  None of {} are in {}."
        expected_reason = expected_reason.format(tags, Release.get_tags(self.db)[0]['candidate'])
        publish.assert_called_once_with(
            topic='update.eject',
            msg={'repo': 'f17-updates', 'update': up,
                 'reason': expected_reason,
                 'request': UpdateRequest.testing,
                 'release': t.compose.release, 'agent': 'bowlofeggs'},
            force=True)
        # The update should have been removed from t.updates
        self.db.expire(t.compose, ['updates'])
        self.assertEqual(len(t.compose.updates), 0)
        self.assert_sems(0)


class TestComposerThread_eject_from_mash(ComposerThreadBaseTestCase):
    """This test class contains tests for the ComposerThread.eject_from_mash() method."""
    @mock.patch('bodhi.server.notifications.publish')
    def test_testing_request(self, publish):
        """
        Assert correct behavior when the update's request is set to testing.
        """
        up = self.db.query(Update).one()
        up.request = UpdateRequest.testing
        self.db.commit()
        msg = self._make_msg()
        t = ComposerThread(self.semmock, msg['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        # t.work() would normally set these up for us, so we'll just fake it
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.db = self.Session()
        t.id = getattr(self.db.query(Release).one(), '{}_tag'.format('stable'))
        up = self.db.query(Update).one()

        t.eject_from_mash(up, 'This update is unacceptable!')

        self.assertEqual(buildsys.DevBuildsys.__untag__,
                         [(u'f17-updates-testing-pending', u'bodhi-2.0-1.fc17')])
        up = self.db.query(Update).one()
        publish.assert_called_once_with(
            topic='update.eject',
            msg={'repo': 'f17-updates', 'update': up,
                 'reason': 'This update is unacceptable!', 'request': UpdateRequest.testing,
                 'release': t.compose.release, 'agent': 'bowlofeggs'},
            force=True)
        # The update should have been removed from t.updates
        self.assertEqual(len(t.compose.updates), 0)

        self.assert_sems(0)


class TestComposerThread_load_state(ComposerThreadBaseTestCase):
    """This test class contains tests for the ComposerThread.load_state() method."""
    def test_with_completed_repo(self):
        """Test when there is a completed_repo in the checkpoints."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = self.db.query(Compose).one()
        t.compose.checkpoints = json.dumps({'other': 'checkpoint', 'completed_repo': '/path/to/it'})
        t.db = self.db

        t.load_state()

        self.assertEqual(t._checkpoints, {'other': 'checkpoint', 'completed_repo': '/path/to/it'})

        self.assert_sems(0)


class TestPungiComposerThread_load_state(ComposerThreadBaseTestCase):
    """This test class contains tests for the PungiComposerThread.load_state() method."""
    def test_with_completed_repo(self):
        """Test when there is a completed_repo in the checkpoints."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = self.db.query(Compose).one()
        t.compose.checkpoints = json.dumps({'other': 'checkpoint', 'completed_repo': '/path/to/it'})
        t.db = self.db

        t.load_state()

        self.assertEqual(t._checkpoints, {'other': 'checkpoint', 'completed_repo': '/path/to/it'})
        self.assertEqual(t.path, '/path/to/it')

        self.assert_sems(0)

    def test_without_completed_repo(self):
        """Test when there is not a completed_repo in the checkpoints."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = self.db.query(Compose).one()
        t.compose.checkpoints = json.dumps({'other': 'checkpoint'})
        t.db = self.db

        t.load_state()

        self.assertEqual(t._checkpoints, {'other': 'checkpoint'})
        self.assertEqual(t.path, None)

        self.assert_sems(0)


class TestComposerThread_remove_state(ComposerThreadBaseTestCase):
    """Test the remove_state() method."""
    def test_remove_state(self):
        """Assert that remove_state() deletes the Compose."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.db = self.db

        t.remove_state()

        self.db.flush()
        self.assertEqual(self.db.query(Compose).count(), 0)

        self.assert_sems(0)


class TestComposerThread_save_state(ComposerThreadBaseTestCase):
    """This test class contains tests for the ComposerThread.save_state() method."""
    def test_with_state(self):
        """Test the optional state parameter."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = self.db.query(Compose).one()
        t.db = self.db
        t.db.commit = mock.MagicMock()

        t.save_state(ComposeState.notifying)

        compose = self.db.query(Compose).one()
        self.assertEqual(compose.state, ComposeState.notifying)
        self.assertEqual(json.loads(compose.checkpoints), {'cool': 'checkpoint'})
        t.db.commit.assert_called_once_with()

    def test_without_state(self):
        """Test without the optional state parameter."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = self.db.query(Compose).one()
        t.db = self.db
        t.db.commit = mock.MagicMock()

        t.save_state()

        compose = self.db.query(Compose).one()
        self.assertEqual(compose.state, ComposeState.requested)
        self.assertEqual(json.loads(compose.checkpoints), {'cool': 'checkpoint'})
        t.db.commit.assert_called_once_with()


class TestPungiComposerThread__wait_for_sync(ComposerThreadBaseTestCase):
    """This test class contains tests for the PungiComposerThread._wait_for_sync() method."""
    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml'})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep',
                mock.MagicMock(side_effect=Exception('This should not happen during this test.')))
    @mock.patch('bodhi.server.consumers.masher.urllib2.urlopen',
                return_value=StringIO('---\nyaml: rules'))
    def test_checksum_match_immediately(self, urlopen, publish):
        """
        Assert correct operation when the repomd checksum matches immediately.
        """
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        t._wait_for_sync()

        expected_calls = [
            mock.call(topic='mashtask.sync.wait', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True),
            mock.call(topic='mashtask.sync.done', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True)]
        publish.assert_has_calls(expected_calls)
        self.assertEqual(urlopen.call_count, 1)
        # Since os.listdir() isn't deterministic about the order of the items it returns, the test
        # won't be deterministic about which of these URLs get called. However, either one of them
        # would be correct so we will just assert that one of them is called.
        expected_calls = [
            mock.call('http://example.com/pub/fedora/linux/updates/testing/17/x86_64/'
                      'repodata.repomd.xml'),
            mock.call('http://example.com/pub/fedora/linux/updates/testing/17/aarch64/'
                      'repodata.repomd.xml')]
        self.assertTrue(urlopen.mock_calls[0] in expected_calls)

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml'})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep',
                mock.MagicMock(side_effect=Exception('This should not happen during this test.')))
    @mock.patch('bodhi.server.consumers.masher.urllib2.urlopen',
                return_value=StringIO('---\nyaml: rules'))
    def test_no_checkarch(self, urlopen, publish):
        """
        Assert error when no checkarch is found.
        """
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['source']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        try:
            t._wait_for_sync()
            assert False, "Compose with just source passed"
        except Exception as ex:
            assert str(ex) == "Not found an arch to _wait_for_sync with"

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml'})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep')
    @mock.patch(
        'bodhi.server.consumers.masher.urllib2.urlopen',
        side_effect=[StringIO('wrong'), StringIO('nope'), StringIO('---\nyaml: rules')])
    def test_checksum_match_third_try(self, urlopen, sleep, publish):
        """
        Assert correct operation when the repomd checksum matches on the third try.
        """
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        t._wait_for_sync()

        expected_calls = [
            mock.call(topic='mashtask.sync.wait', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True),
            mock.call(topic='mashtask.sync.done', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True)]
        publish.assert_has_calls(expected_calls)
        # Since os.listdir() isn't deterministic about the order of the items it returns, the test
        # won't be deterministic about which of arch URL gets used. However, either one of them
        # would be correct so we will just assert that the one that is used is used correctly.
        arch = 'x86_64' if 'x86_64' in urlopen.mock_calls[0][1][0] else 'aarch64'
        expected_calls = [
            mock.call('http://example.com/pub/fedora/linux/updates/testing/17/'
                      '{}/repodata.repomd.xml'.format(arch))
            for i in range(3)]
        urlopen.assert_has_calls(expected_calls)
        sleep.assert_has_calls([mock.call(200), mock.call(200)])

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml'})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep')
    @mock.patch(
        'bodhi.server.consumers.masher.urllib2.urlopen',
        side_effect=[HTTPError('url', 404, 'Not found', {}, None),
                     StringIO('---\nyaml: rules')])
    def test_httperror(self, urlopen, sleep, publish):
        """
        Assert that an HTTPError is properly caught and logged, and that the algorithm continues.
        """
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.log = mock.MagicMock()
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        t._wait_for_sync()

        expected_calls = [
            mock.call(topic='mashtask.sync.wait', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True),
            mock.call(topic='mashtask.sync.done', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True)]
        publish.assert_has_calls(expected_calls)
        # Since os.listdir() isn't deterministic about the order of the items it returns, the test
        # won't be deterministic about which of arch URL gets used. However, either one of them
        # would be correct so we will just assert that the one that is used is used correctly.
        arch = 'x86_64' if 'x86_64' in urlopen.mock_calls[0][1][0] else 'aarch64'
        expected_calls = [
            mock.call('http://example.com/pub/fedora/linux/updates/testing/17/'
                      '{}/repodata.repomd.xml'.format(arch))
            for i in range(2)]
        urlopen.assert_has_calls(expected_calls)
        t.log.exception.assert_called_once_with('Error fetching repomd.xml')
        sleep.assert_called_once_with(200)

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd': None})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep',
                mock.MagicMock(side_effect=Exception('This should not happen during this test.')))
    @mock.patch('bodhi.server.consumers.masher.urllib2.urlopen',
                mock.MagicMock(side_effect=Exception('urlopen should not be called')))
    def test_missing_config_key(self, publish):
        """
        Assert that a ValueError is raised when the needed *_master_repomd config is missing.
        """
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        with self.assertRaises(ValueError) as exc:
            t._wait_for_sync()

        self.assertEqual(six.text_type(exc.exception),
                         'Could not find any of fedora_17_testing_master_repomd,'
                         'fedora_testing_master_repomd in the config file')
        publish.assert_called_once_with(topic='mashtask.sync.wait',
                                        msg={'repo': t.id, 'agent': 'bowlofeggs'}, force=True)

    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep',
                mock.MagicMock(side_effect=Exception('This should not happen during this test.')))
    @mock.patch('bodhi.server.consumers.masher.urllib2.urlopen',
                mock.MagicMock(side_effect=Exception('urlopen should not be called')))
    def test_missing_repomd(self, publish):
        """
        Assert that an error is logged when the local repomd is missing.
        """
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.log = mock.MagicMock()
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        repodata = os.path.join(t.path, 'compose', 'Everything', 'x86_64', 'os', 'repodata')
        os.makedirs(repodata)

        t._wait_for_sync()

        publish.assert_called_once_with(topic='mashtask.sync.wait',
                                        msg={'repo': t.id, 'agent': 'bowlofeggs'}, force=True)
        t.log.error.assert_called_once_with(
            'Cannot find local repomd: %s', os.path.join(repodata, 'repomd.xml'))

    @unittest.skipIf(six.PY3, 'Not working with Python 3 yet')
    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml'})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep')
    @mock.patch(
        'bodhi.server.consumers.masher.urllib2.urlopen',
        side_effect=[URLError('it broke'),
                     StringIO('---\nyaml: rules')])
    def test_urlerror(self, urlopen, sleep, publish):
        """
        Assert that a URLError is properly caught and logged, and that the algorithm continues.
        """
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.log = mock.MagicMock()
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        t._wait_for_sync()

        expected_calls = [
            mock.call(topic='mashtask.sync.wait', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True),
            mock.call(topic='mashtask.sync.done', msg={'repo': t.id, 'agent': 'bowlofeggs'},
                      force=True)]
        publish.assert_has_calls(expected_calls)
        # Since os.listdir() isn't deterministic about the order of the items it returns, the test
        # won't be deterministic about which of arch URL gets used. However, either one of them
        # would be correct so we will just assert that the one that is used is used correctly.
        arch = 'x86_64' if 'x86_64' in urlopen.mock_calls[0][1][0] else 'aarch64'
        expected_calls = [
            mock.call('http://example.com/pub/fedora/linux/updates/testing/17/'
                      '{}/repodata.repomd.xml'.format(arch))
            for i in range(2)]
        urlopen.assert_has_calls(expected_calls)
        t.log.exception.assert_called_once_with('Error fetching repomd.xml')
        sleep.assert_called_once_with(200)


class TestComposerThread__mark_status_changes(ComposerThreadBaseTestCase):
    """Test the _mark_status_changes() method."""
    def test_stable_update(self):
        """Assert that a stable update gets the right status."""
        update = Update.query.one()
        update.status = UpdateStatus.testing
        update.request = UpdateRequest.stable
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()

        t._mark_status_changes()

        update = Update.query.one()
        self.assertEqual(update.status, UpdateStatus.stable)
        # The request is removed by the _unlock_updates() method, which is called later than this
        # one.
        self.assertEqual(update.request, UpdateRequest.stable)
        now = datetime.datetime.utcnow()
        self.assertTrue((now - update.date_stable) < datetime.timedelta(seconds=5))
        self.assertIsNone(update.date_testing)
        self.assertTrue((now - update.date_pushed) < datetime.timedelta(seconds=5))
        self.assertTrue(update.pushed)

    def test_testing_update(self):
        """Assert that a testing update gets the right status."""
        update = Update.query.one()
        update.status = UpdateStatus.pending
        update.request = UpdateRequest.testing
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()

        t._mark_status_changes()

        update = Update.query.one()
        self.assertEqual(update.status, UpdateStatus.testing)
        # The request is removed by the _unlock_updates() method, which is called later than this
        # one.
        self.assertEqual(update.request, UpdateRequest.testing)
        now = datetime.datetime.utcnow()
        self.assertTrue((now - update.date_testing) < datetime.timedelta(seconds=5))
        self.assertIsNone(update.date_stable)
        self.assertTrue((now - update.date_pushed) < datetime.timedelta(seconds=5))
        self.assertTrue(update.pushed)


class TestComposerThread_send_notifications(ComposerThreadBaseTestCase):
    """Test ComposerThread.send_notifications."""

    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    def test_getlogin_raising_oserror(self, publish):
        """Assert that "masher" is used as the agent if getlogin() raises OSError."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()

        with mock.patch('bodhi.server.consumers.masher.os.getlogin', side_effect=OSError()):
            t.send_notifications()

        # The agent should be "masher" since OSError was raised.
        self.assertEqual(publish.mock_calls[0][2]['msg']['agent'], 'masher')


class TestComposerThread_send_testing_digest(ComposerThreadBaseTestCase):
    """Test ComposerThread.send_testing_digest()."""

    @mock.patch('bodhi.server.mail.smtplib.SMTP')
    def test_critpath_updates(self, SMTP):
        """If there are critical path updates, the maildata should mention it."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        update = t.compose.updates[0]
        update.critpath = True
        update.request = None
        update.status = UpdateStatus.testing
        t.testing_digest = {'Fedora 17': {'fake': 'content'}}
        t._checkpoints = {}
        t.db = self.Session
        self.db.flush()

        with mock.patch.dict(config, {'smtp_server': 'smtp.example.com'}):
            t.send_testing_digest()

        SMTP.assert_called_once_with('smtp.example.com')
        sendmail = SMTP.return_value.sendmail
        self.assertEqual(sendmail.call_count, 1)
        args = sendmail.mock_calls[0][1]
        self.assertEqual(args[0].decode('utf-8'), config['bodhi_email'])
        self.assertEqual([c.decode('utf-8') for c in args[1]],
                         [config['fedora_test_announce_list']])
        self.assertTrue(
            'The following Fedora 17 Critical Path updates have yet to be approved:\n Age URL\n'
            in args[2].decode('utf-8'))
        self.assertTrue(str(update.days_in_testing) in args[2].decode('utf-8'))
        self.assertTrue(update.abs_url() in args[2].decode('utf-8'))
        self.assertTrue(update.title in args[2].decode('utf-8'))

    @mock.patch('bodhi.server.mail.smtplib.SMTP')
    def test_security_updates(self, SMTP):
        """If there are security updates, the maildata should mention it."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        update = t.compose.updates[0]
        update.type = UpdateType.security
        update.request = None
        update.status = UpdateStatus.testing
        t.testing_digest = {'Fedora 17': {'fake': 'content'}}
        t._checkpoints = {}
        t.db = self.Session
        self.db.flush()

        with mock.patch.dict(config, {'smtp_server': 'smtp.example.com'}):
            t.send_testing_digest()

        SMTP.assert_called_once_with('smtp.example.com')
        sendmail = SMTP.return_value.sendmail
        self.assertEqual(sendmail.call_count, 1)
        args = sendmail.mock_calls[0][1]
        self.assertEqual(args[0].decode('utf-8'), config['bodhi_email'])
        self.assertEqual([c.decode('utf-8') for c in args[1]],
                         [config['fedora_test_announce_list']])
        self.assertTrue(
            'The following Fedora 17 Security updates need testing:\n Age  URL\n'
            in args[2].decode('utf-8'))
        self.assertTrue(str(update.days_in_testing) in args[2].decode('utf-8'))
        self.assertTrue(update.abs_url() in args[2].decode('utf-8'))
        self.assertTrue(update.title in args[2].decode('utf-8'))

    @mock.patch('bodhi.server.consumers.masher.log.warn')
    def test_test_list_not_configured(self, warn):
        """If a test_announce_list setting is not found, a warning should be logged."""
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.testing_digest = {'Fedora 17': {'fake': 'content'}}
        t._checkpoints = {}
        t.db = self.Session

        with mock.patch.dict(config, {'fedora_test_announce_list': None}):
            t.send_testing_digest()

        warn.assert_called_once_with(
            '%r undefined. Not sending updates-testing digest', 'fedora_test_announce_list')


class TestComposerThread__unlock_updates(ComposerThreadBaseTestCase):
    """Test the _unlock_updates() method."""
    def test__unlock_updates(self):
        """Assert that _unlock_updates() works correctly."""
        update = Update.query.one()
        update.request = UpdateRequest.testing
        t = ComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                           'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()

        t._unlock_updates()

        update = Update.query.one()
        self.assertIsNone(update.request)
        self.assertFalse(update.locked)


class TestPungiComposerThread__punge(ComposerThreadBaseTestCase):
    """Test the PungiComposerThread._punge() method."""

    @mock.patch('bodhi.server.consumers.masher.subprocess.Popen')
    def test_skips_if_path_defined(self, Popen):
        """_punge should log a message and skip running if path is truthy."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'bowlofeggs', log, self.Session, self.tempdir)
        t.log.info = mock.MagicMock()
        t.path = '/some/path'

        t._punge()

        t.log.info.assert_called_once_with('Skipping completed repo: %s', '/some/path')
        # Popen() should not have been called since we should have skipping running pungi.
        self.assertEqual(Popen.call_count, 0)


class TestPungiComposerThread__stage_repo(ComposerThreadBaseTestCase):
    """Test PungiComposerThread._stage_repo()."""

    def test_old_link_present(self):
        """If a link from the last run is still present, no error should be raised."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'ralph', log, self.Session, self.tempdir)
        t.id = 'f17-updates-testing'
        t.log.info = mock.MagicMock()
        t.path = os.path.join(self.tempdir, 'latest-f17-updates-testing')
        stage_dir = os.path.join(self.tempdir, 'stage_dir')
        os.makedirs(t.path)
        os.mkdir(stage_dir)
        link = os.path.join(stage_dir, t.id)
        os.symlink(t.path, link)

        with mock.patch.dict(config, {'mash_stage_dir': stage_dir}):
            t._stage_repo()

        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), t.path)
        self.assertEqual(
            t.log.info.mock_calls,
            [mock.call('Creating symlink: %s => %s' % (link, t.path))])

    def test_stage_dir_de(self):
        """Test for when stage_dir does exist."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'ralph', log, self.Session, self.tempdir)
        t.id = 'f17-updates-testing'
        t.log.info = mock.MagicMock()
        t.path = os.path.join(self.tempdir, 'latest-f17-updates-testing')
        stage_dir = os.path.join(self.tempdir, 'stage_dir')
        os.makedirs(t.path)
        os.mkdir(stage_dir)

        with mock.patch.dict(config, {'mash_stage_dir': stage_dir}):
            t._stage_repo()

        link = os.path.join(stage_dir, t.id)
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), t.path)
        self.assertEqual(
            t.log.info.mock_calls,
            [mock.call('Creating symlink: %s => %s' % (link, t.path))])

    def test_stage_dir_dne(self):
        """Test for when stage_dir does not exist."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'ralph', log, self.Session, self.tempdir)
        t.id = 'f17-updates-testing'
        t.log.info = mock.MagicMock()
        t.path = os.path.join(self.tempdir, 'latest-f17-updates-testing')
        stage_dir = os.path.join(self.tempdir, 'stage_dir')
        os.makedirs(t.path)

        with mock.patch.dict(config, {'mash_stage_dir': stage_dir}):
            t._stage_repo()

        link = os.path.join(stage_dir, t.id)
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), t.path)
        self.assertEqual(
            t.log.info.mock_calls,
            [mock.call('Creating mash_stage_dir %s', stage_dir),
             mock.call('Creating symlink: %s => %s' % (link, t.path))])


class TestPungiComposerThread__wait_for_repo_signature(ComposerThreadBaseTestCase):
    """Test PungiComposerThread._wait_for_repo_signature()."""

    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    def test_dont_wait_for_signatures(self, publish):
        """Test that if wait_for_repo_sig is disabled, nothing happens."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'ralph', log, self.Session, self.tempdir)
        t.id = 'f17-updates-testing'
        t.path = os.path.join(self.tempdir, 'latest-f17-updates-testing')
        t.log.info = mock.MagicMock()

        with mock.patch.dict(config, {'wait_for_repo_sig': False}):
            t._wait_for_repo_signature()

        publish.assert_called_once_with(topic='repo.done',
                                        force=True,
                                        msg={'repo': t.id,
                                             'path': t.path,
                                             'agent': 'ralph'})
        self.assertEqual(
            t.log.info.mock_calls,
            [mock.call('Not waiting for a repo signature')])

    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('os.path.exists', side_effect=[
        # First time, none of the signatures exist
        False, False, False,
        # Second time, we have two sets of signatures
        True, False, True,
        # Third time, we get all signatures and proceed
        True, True, True
    ])
    @mock.patch('bodhi.server.consumers.masher.PungiComposerThread.save_state')
    @mock.patch('time.sleep')
    @mock.patch('os.listdir', return_value=['x86_64', 'aarch64', 'source'])
    def test_wait_for_signatures(self, listdir, sleep, save, exists, publish):
        """Test that if wait_for_repo_sig is disabled, nothing happens."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'ralph', log, self.Session, self.tempdir)
        t.id = 'f17-updates-testing'
        t.path = '/composepath'
        t.log.info = mock.MagicMock()

        with mock.patch.dict(config, {'wait_for_repo_sig': True}):
            t._wait_for_repo_signature()

        self.assertEqual(len(sleep.mock_calls), 2)
        self.assertEqual(
            t.log.info.mock_calls,
            [mock.call("Waiting for signatures in %s",
                       "/composepath/compose/Everything/x86_64/os/repodata/repomd.xml.asc, "
                       "/composepath/compose/Everything/aarch64/os/repodata/repomd.xml.asc, "
                       "/composepath/compose/Everything/source/tree/repodata/repomd.xml.asc"),
             mock.call('Waiting on %s',
                       "/composepath/compose/Everything/x86_64/os/repodata/repomd.xml.asc, "
                       "/composepath/compose/Everything/aarch64/os/repodata/repomd.xml.asc, "
                       "/composepath/compose/Everything/source/tree/repodata/repomd.xml.asc"),
             mock.call('Waiting on %s',
                       "/composepath/compose/Everything/aarch64/os/repodata/repomd.xml.asc"),
             mock.call('All signatures were created')])
        self.assertEqual(
            exists.mock_calls,
            [mock.call('/composepath/compose/Everything/x86_64/os/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/aarch64/os/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/source/tree/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/x86_64/os/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/aarch64/os/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/source/tree/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/x86_64/os/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/aarch64/os/repodata/repomd.xml.asc'),
             mock.call('/composepath/compose/Everything/source/tree/repodata/repomd.xml.asc')])
        save.assert_called_once_with(ComposeState.signing_repo)
        publish.assert_called_once_with(topic='repo.done',
                                        force=True,
                                        msg={'repo': t.id,
                                             'path': t.path,
                                             'agent': 'ralph'})


class TestPungiComposerThread__wait_for_pungi(ComposerThreadBaseTestCase):
    """Test PungiComposerThread._wait_for_pungi()."""

    def test_pungi_process_None(self):
        """If pungi_process is None, a log should be written and the method should return."""
        t = PungiComposerThread(self.semmock, self._make_msg()['body']['msg']['composes'][0],
                                'ralph', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.db = self.Session
        t.log.info = mock.MagicMock()
        t._checkpoints = {}

        t._wait_for_pungi(None)

        self.assertEqual(
            t.log.info.mock_calls,
            [mock.call('Compose object updated.'),
             mock.call('Not waiting for pungi thread, as there was no pungi')])
        self.assertEqual(t.compose.state, ComposeState.punging)
