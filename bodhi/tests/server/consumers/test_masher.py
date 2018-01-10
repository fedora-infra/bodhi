# -*- coding: utf-8 -*-
# Copyright © 2007-2017 Red Hat, Inc.
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
from cStringIO import StringIO
import datetime
import dummy_threading
import errno
import json
import os
import shutil
import tempfile
import time
import unittest
import urllib2
import urlparse

from click import testing
import mock
import six

from bodhi.server import buildsys, exceptions, log, push
from bodhi.server.config import config
from bodhi.server.consumers.masher import (
    checkpoint, Masher, MasherThread, RPMMasherThread, ModuleMasherThread)
from bodhi.server.exceptions import LockedUpdateException
from bodhi.server.models import (
    Build, BuildrootOverride, Compose, ComposeState, Release, ReleaseState, RpmBuild,
    TestGatingStatus, Update, UpdateRequest, UpdateStatus, UpdateType, User, ModuleBuild,
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

        # Since the MasherThread is a subclass of Thread and since it is already constructed before
        # we have a chance to alter it, we need to change its superclass to be
        # dummy_threading.Thread so that the test suite doesn't launch real Threads. Threads cannot
        # use the same database sessions, and that means that changes that threads make will not
        # appear in other thread's sessions, which cause a lot of problems in these tests.
        # Mock was not able to make this change since the __bases__ attribute cannot be removed, but
        # we don't really need this to be cleaned up since we don't want any tests launching theads
        # anyway.
        MasherThread.__bases__ = (dummy_threading.Thread,)
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

    def tearDown(self):
        super(TestMasher, self).tearDown()
        shutil.rmtree(self.tempdir)
        shutil.rmtree(self._new_mash_stage_dir)

    def set_stable_request(self, title):
        with self.db_factory() as session:
            query = session.query(Update).filter_by(title=title)
            update = query.one()
            update.request = UpdateRequest.stable
            session.flush()

    def _generate_fake_pungi(self, masher_thread, tag, release):
        """
        Return a function that is suitable for mock to replace the call to Popen that run Pungi.

        Args:
            masher_thread (bodhi.server.consumers.masher.MasherThread): The MasherThread that Pungi
                is running inside.
            tag (basestring): The type of tag you wish to mash ("stable_tag" or "testing_tag").
            release (bodhi.server.models.Release): The Release you are mashing.
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

            # We need to fake Pungi having run or wait_for_mash() will fail to find the output dir
            reqtype = 'updates' if tag == 'stable_tag' else 'updates-testing'
            mash_dir = os.path.join(
                masher_thread.mash_dir,
                '%s-%d-%s-%s.0' % (release.id_prefix.title(),
                                   int(release.version),
                                   reqtype,
                                   time.strftime("%Y%m%d")))

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

            fake_popen = mock.MagicMock()
            fake_popen.communicate = lambda: (mock.MagicMock(), 'hello')
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
        self.assertEquals(len(publish.call_args_list), 0)

    @mock.patch('bodhi.server.notifications.publish')
    def test_push_invalid_compose(self, publish):
        msg = self._make_msg()
        msg['body']['msg']['composes'][0]['release_id'] = 65535

        with self.assertRaises(Exception) as exc:
            self.masher.consume(msg)

        self.assertEqual(str(exc.exception), 'No row was found for one()')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch.object(MasherThread, 'determine_and_perform_tag_actions', mock_exc)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_locking(self, publish, *args):
        with self.db_factory() as session:
            up = session.query(Update).one()
            up.locked = False

        self.masher.consume(self._make_msg())

        # Ensure that fedmsg was called 4 times
        self.assertEquals(len(publish.call_args_list), 3)

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
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_tags(self, publish, *args):
        # Make the build a buildroot override as well
        with self.db_factory() as session:
            release = session.query(Update).one().release
            build = session.query(Build).one()
            nvr = build.nvr
            pending_testing_tag = release.pending_testing_tag
            override_tag = release.override_tag
            self.koji.__tagged__[session.query(Update).first().title] = [release.override_tag,
                                                                         pending_testing_tag]

        # Start the push
        self.masher.consume(self._make_msg())

        # Ensure that fedmsg was called 3 times
        self.assertEquals(len(publish.call_args_list), 4)
        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=True,
                     ctype='rpm',
                     repo='f17-updates-testing',
                     agent='bowlofeggs'),
            force=True)

        # Ensure our single update was moved
        self.assertEquals(len(self.koji.__moved__), 1)
        self.assertEquals(len(self.koji.__added__), 0)
        self.assertEquals(self.koji.__moved__[0],
                          (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-1.fc17'))

        # The override tag won't get removed until it goes to stable
        self.assertEquals(self.koji.__untag__[0], (pending_testing_tag, nvr))
        self.assertEquals(len(self.koji.__untag__), 1)

        with self.db_factory() as session:
            # Set the update request to stable and the release to pending
            up = session.query(Update).one()
            up.release.state = ReleaseState.pending
            up.request = UpdateRequest.stable

        self.koji.clear()

        self.masher.consume(self._make_msg())

        # Ensure that stable updates to pending releases get their
        # tags added, not removed
        self.assertEquals(len(self.koji.__moved__), 0)
        self.assertEquals(len(self.koji.__added__), 1)
        self.assertEquals(self.koji.__added__[0], (u'f17', u'bodhi-2.0-1.fc17'))
        self.assertEquals(self.koji.__untag__[0], (override_tag, u'bodhi-2.0-1.fc17'))

        # Check that the override got expired
        with self.db_factory() as session:
            ovrd = session.query(BuildrootOverride).one()
            self.assertIsNotNone(ovrd.expired_date)

            # Check that the request_complete method got run
            up = session.query(Update).one()
            self.assertIsNone(up.request)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_tag_ordering(self, publish, *args):
        """
        Test pushing a batch of updates with multiple builds for the same package.
        Ensure that the latest version is tagged last.
        """
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
        self.assertEquals(len(publish.call_args_list), 5)
        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=True,
                     ctype='rpm',
                     repo='f17-updates-testing',
                     agent='bowlofeggs'),
            force=True)

        # Ensure our two updates were moved
        self.assertEquals(len(self.koji.__moved__), 2)
        self.assertEquals(len(self.koji.__added__), 0)

        # Ensure the most recent version is tagged last in order to be the 'koji latest-pkg'
        self.assertEquals(self.koji.__moved__[0],
                          (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-1.fc17'))
        self.assertEquals(self.koji.__moved__[1],
                          (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-2.fc17'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.mail._send_mail')
    def test_testing_digest(self, mail, *args):
        t = RPMMasherThread(self._make_msg()['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)

        t.run()

        self.assertEquals(t.testing_digest[u'Fedora 17'][u'bodhi-2.0-1.fc17'], """\
================================================================================
 libseccomp-2.1.0-1.fc20 (FEDORA-%s-a3bbe1a8f2)
 Enhanced seccomp library
--------------------------------------------------------------------------------
Update Information:

Useful details!
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
             '----------------------------\nReferences:\n\n  [ 1 ] Bug #12345 - None\n        '
             'https://bugzilla.redhat.com/show_bug.cgi?id=12345\n  [ 2 ] CVE-1985-0110\n        '
             'http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-1985-0110\n--------------------'
             '------------------------------------------------------------\n\n') % (
                config.get('fedora_test_announce_list'), time.strftime('%Y'))), repr(body)

    @mock.patch('bodhi.server.consumers.masher.MasherThread.save_state')
    def test_mash_no_found_dirs(self, save_state):
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = Compose.from_dict(session, msg['body']['msg']['composes'][0])
            t.release = session.query(Release).filter_by(name=u'F17').one()
            try:
                fake_popen = mock.MagicMock()
                fake_popen.communicate = lambda: (mock.MagicMock(), 'hello')
                fake_popen.poll.return_value = None
                fake_popen.returncode = 0
                t._startyear = datetime.datetime.utcnow().year
                t.wait_for_mash(fake_popen)
                assert False, "Mash without generated dirs did not crash"
            except Exception as ex:
                expected_error = ('We were unable to find a path with prefix '
                                  'Fedora-17-updates-testing-{}* in mashdir')
                expected_error = expected_error.format(datetime.datetime.utcnow().year)
                assert str(ex) == expected_error
            t.db = None

    @mock.patch('bodhi.server.consumers.masher.MasherThread.save_state')
    def test_sanity_check_no_arches(self, save_state):
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t.wait_for_mash(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
            t.db = None

        # test without any arches
        try:
            t.sanity_check_repo()
            assert False, "Sanity check didn't fail with empty dir"
        except Exception:
            pass

    @mock.patch('bodhi.server.consumers.masher.MasherThread.save_state')
    def test_sanity_check_valid(self, save_state):
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t.wait_for_mash(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
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

        t.sanity_check_repo()

    @mock.patch('bodhi.server.consumers.masher.MasherThread.save_state')
    def test_sanity_check_broken_repodata(self, save_state):
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._startyear = datetime.datetime.utcnow().year
            t._checkpoints = {}
            t.wait_for_mash(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
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

        try:
            t.sanity_check_repo()
            assert False, 'Busted metadata passed'
        except exceptions.RepodataException:
            pass

        save_state.assert_called_once_with(ComposeState.punging)

    @mock.patch('bodhi.server.consumers.masher.MasherThread.save_state')
    def test_sanity_check_symlink(self, save_state):
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t.wait_for_mash(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
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

        try:
            t.sanity_check_repo()
            assert False, "Symlinks passed"
        except Exception as ex:
            assert str(ex) == "Symlinks found"

    @mock.patch('bodhi.server.consumers.masher.MasherThread.save_state')
    def test_sanity_check_directories_missing(self, save_state):
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)
        t.devnull = mock.MagicMock()
        t.id = 'f17-updates-testing'
        with self.db_factory() as session:
            t.db = session
            t.compose = session.query(Compose).one()
            t._checkpoints = {}
            t._startyear = datetime.datetime.utcnow().year
            t.wait_for_mash(self._generate_fake_pungi(t, 'testing_tag', t.compose.release)())
            t.db = None

        # test with valid repodata
        for arch in ('i386', 'x86_64', 'armhfp'):
            repo = os.path.join(t.path, 'compose', 'Everything', arch, 'os')
            mkmetadatadir(repo)
            shutil.rmtree(os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'Packages'))

        mkmetadatadir(os.path.join(t.path, 'compose', 'Everything', 'source', 'tree'))

        try:
            t.sanity_check_repo()
            assert False, "Missing directories passed"
        except OSError as oex:
            assert oex.errno == errno.ENOENT

    def test_stage(self):
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'ralph', log, self.db_factory, self.tempdir)
        t.id = 'f17-updates-testing'
        t.path = os.path.join(self.tempdir, 'latest-f17-updates-testing')
        os.makedirs(t.path)
        t.stage_repo()
        stage_dir = config.get('mash_stage_dir')
        link = os.path.join(stage_dir, t.id)
        self.assertTrue(os.path.islink(link))
        assert os.readlink(link) == t.path

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_security_update_priority(self, publish, *args):
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
        self.assertEquals(calls[1], mock.call(
            force=True,
            msg={'repo': u'f18-updates',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc18'],
                 'agent': 'bowlofeggs'},
            topic='mashtask.mashing'))
        self.assertEquals(calls[4], mock.call(
            force=True,
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f18-updates',
                 'agent': 'bowlofeggs'},
            topic='mashtask.complete'))
        self.assertEquals(calls[5], mock.call(
            force=True,
            msg={'repo': u'f17-updates-testing',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc17'],
                 'agent': 'bowlofeggs'},
            topic='mashtask.mashing'))
        self.assertEquals(calls[-1], mock.call(
            force=True,
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f17-updates-testing',
                 'agent': 'bowlofeggs'},
            topic='mashtask.complete'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_security_update_priority_testing(self, publish, *args):
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
        self.assertEquals(calls[1], mock.call(
            msg={'repo': u'f17-updates-testing',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc17'],
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.mashing'))
        self.assertEquals(calls[3], mock.call(
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f17-updates-testing',
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.complete'))
        self.assertEquals(calls[4], mock.call(
            msg={'repo': u'f18-updates',
                 'ctype': 'rpm',
                 'updates': [u'bodhi-2.0-1.fc18'],
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.mashing'))
        self.assertEquals(calls[-1], mock.call(
            msg={'success': True,
                 'ctype': 'rpm',
                 'repo': 'f18-updates',
                 'agent': 'bowlofeggs'},
            force=True,
            topic='mashtask.complete'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_security_updates_parallel(self, publish, *args):
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
            self.assertEquals(
                calls[2],
                mock.call(msg={'repo': u'f17-updates',
                               'ctype': 'rpm',
                               'updates': [u'bodhi-2.0-1.fc17'],
                               'agent': 'bowlofeggs'},
                          force=True, topic='mashtask.mashing'))
        elif calls[1] == self.assertEquals(
                calls[1],
                mock.call(
                    msg={'repo': u'f17-updates',
                         'ctype': 'rpm',
                         'updates': [u'bodhi-2.0-1.fc17'],
                         'agent': 'bowlofeggs'},
                    force=True, topic='mashtask.mashing')):
            self.assertEquals(
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
        t = MasherThread(msg['body']['msg']['composes'][0], 'ralph', log, self.db_factory,
                         self.tempdir)

        with self.assertRaises(NotImplementedError):
            t.copy_additional_pungi_files(None, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch.dict(
        config,
        {'pungi.cmd': '/usr/bin/false'})
    def test_mash_early_exit(self, publish, *args):
        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)

        t.run()

        self.assertFalse(t.success)
        with self.db_factory() as db:
            compose = Compose.from_dict(db, msg['body']['msg']['composes'][0])
            self.assertEqual(compose.state, ComposeState.failed)
            self.assertEqual(compose.error_message, 'Pungi returned error, aborting!')
        self.assertEqual(t._checkpoints, {'determine_and_perform_tag_actions': True})

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_mash_late_exit(self, publish, *args):
        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)

        with self.db_factory() as session:
            with tempfile.NamedTemporaryFile(delete=False) as script:
                script.write('#!/bin/bash\nsleep 5\nexit 1\n')
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
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_mash(self, publish, *args):
        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)

        with self.db_factory() as session:
            with mock.patch('bodhi.server.consumers.masher.subprocess.Popen') as Popen:
                release = session.query(Release).filter_by(name=u'F17').one()
                Popen.side_effect = self._generate_fake_pungi(t, 'stable_tag', release)
                t.run()

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
                 '--quiet', '--target-dir', t.mash_dir, '--old-composes', t.mash_dir,
                 '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                self.tempdir, 'Fedora-17-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_mash_module(self, publish, *args):
        with self.db_factory() as db:
            user = db.query(User).first()

            release = self.create_release('27M')
            package = Package(name=u'testmodule',
                              type=ContentType.module)
            db.add(package)
            build1 = ModuleBuild(nvr=u'testmodule-master-1',
                                 release=release, signed=True,
                                 package=package)
            db.add(build1)
            build2 = ModuleBuild(nvr=u'testmodule-master-2',
                                 release=release, signed=True,
                                 package=package)
            db.add(build2)
            update = Update(
                title=u'testmodule-master-2',
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
        t = ModuleMasherThread(msg['body']['msg']['composes'][0],
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

        self.assertEqual(
            Popen.mock_calls,
            [mock.call(
                [config['pungi.cmd'], '--config', '{}/pungi.conf'.format(t._pungi_conf_dir),
                 '--quiet', '--target-dir', t.mash_dir, '--old-composes', t.mash_dir,
                 '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                self.tempdir,
                'Fedora-27-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})

    @mock.patch(**mock_failed_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_failed_gating(self, publish, *args):

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMMasherThread(
            msg['body']['msg']['composes'][0], 'ralph', log, self.db_factory, self.tempdir)

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
                 '--quiet', '--target-dir', t.mash_dir, '--old-composes', t.mash_dir,
                 '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                self.tempdir, 'Fedora-17-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})

    @mock.patch(**mock_absent_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_absent_gating(self, publish, *args):
        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()

        t = RPMMasherThread(msg['body']['msg']['composes'][0], 'ralph', log, self.db_factory,
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
                 '--quiet', '--target-dir', t.mash_dir, '--old-composes', t.mash_dir,
                 '--no-latest-link', '--label', t._label],
                cwd=t.mash_dir, shell=False, stderr=-1,
                stdin=mock.ANY,
                stdout=mock.ANY)])
        d = datetime.datetime.utcnow()
        self.assertEqual(
            t._checkpoints,
            {'completed_repo': os.path.join(
                self.tempdir, 'Fedora-17-updates-{}{:02}{:02}.0'.format(d.year, d.month, d.day)),
             'determine_and_perform_tag_actions': True,
             'modify_bugs': True,
             'send_stable_announcements': True,
             'send_testing_digest': True,
             'status_comments': True})

    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    @mock.patch('bodhi.server.bugs.bugtracker.modified')
    @mock.patch('bodhi.server.bugs.bugtracker.on_qa')
    def test_modify_testing_bugs(self, on_qa, modified, *args):
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
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.bugs.bugtracker.comment')
    @mock.patch('bodhi.server.bugs.bugtracker.close')
    def test_modify_stable_bugs(self, close, comment, *args):
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        msg = self._make_msg()
        t = RPMMasherThread(msg['body']['msg']['composes'][0],
                            'ralph', log, self.db_factory, self.tempdir)

        t.run()

        close.assert_called_with(
            12345,
            versions=dict(bodhi=u'bodhi-2.0-1.fc17'),
            comment=(u'bodhi-2.0-1.fc17 has been pushed to the Fedora 17 stable repository. If '
                     u'problems still persist, please make note of it in this bug report.'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_status_comment_testing(self, *args):
        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEquals(len(up.comments), 2)

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEquals(len(up.comments), 3)
            self.assertEquals(up.comments[-1]['text'], u'This update has been pushed to testing.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_status_comment_stable(self, *args):
        with self.db_factory() as session:
            up = session.query(Update).one()
            up.request = UpdateRequest.stable
            self.assertEquals(len(up.comments), 2)

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEquals(len(up.comments), 3)
            self.assertEquals(up.comments[-1]['text'], u'This update has been pushed to stable.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_get_security_updates(self, *args):
        msg = self._make_msg()
        t = MasherThread(msg['body']['msg']['composes'][0],
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

            self.assertEquals(len(updates), 1)
            self.assertEquals(updates[0].title, u.builds[0].nvr)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_unlock_updates(self, *args):
        with self.db_factory() as session:
            up = session.query(Update).one()
            up.request = UpdateRequest.stable
            self.assertEquals(len(up.comments), 2)

        self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEquals(up.locked, False)
            self.assertEquals(up.status, UpdateStatus.stable)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_resume_push(self, *args):
        with mock.patch.object(MasherThread, 'generate_testing_digest', mock_exc):
            with self.db_factory() as session:
                up = session.query(Update).one()
                up.request = UpdateRequest.testing
                up.status = UpdateStatus.pending

            # Simulate a failed push
            self.masher.consume(self._make_msg())

        # Ensure that the update hasn't changed state
        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEquals(up.request, UpdateRequest.testing)
            self.assertEquals(up.status, UpdateStatus.pending)

        # Resume the push
        msg = self._make_msg()
        msg['body']['msg']['resume'] = True
        self.masher.consume(msg)

        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertEquals(up.status, UpdateStatus.testing)
            self.assertEquals(up.request, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_stable_requirements_met_during_push(self, *args):
        """
        Test reaching the stablekarma threshold while the update is being
        pushed to testing
        """
        # Simulate a failed push
        with mock.patch.object(MasherThread, 'determine_and_perform_tag_actions', mock_exc):
            with self.db_factory() as session:
                up = session.query(Update).one()
                up.request = UpdateRequest.testing
                up.status = UpdateStatus.pending
                self.assertEquals(up.stable_karma, 3)
            self.masher.consume(self._make_msg())

        with self.db_factory() as session:
            up = session.query(Update).one()

            # Ensure the update is still locked and in testing
            self.assertEquals(up.locked, True)
            self.assertEquals(up.status, UpdateStatus.pending)
            self.assertEquals(up.request, UpdateRequest.testing)

            # Have the update reach the stable karma threshold
            self.assertEquals(up.karma, 1)
            up.comment(session, u"foo", 1, u'foo')
            self.assertEquals(up.karma, 2)
            self.assertEquals(up.request, UpdateRequest.testing)
            up.comment(session, u"foo", 1, u'bar')
            self.assertEquals(up.karma, 3)
            self.assertEquals(up.request, UpdateRequest.testing)
            up.comment(session, u"foo", 1, u'biz')
            self.assertEquals(up.request, UpdateRequest.testing)
            self.assertEquals(up.karma, 4)

        # finish push and unlock updates
        msg = self._make_msg()
        msg['body']['msg']['resume'] = True
        self.masher.consume(msg)

        with self.db_factory() as session:
            up = session.query(Update).one()
            up.comment(session, u"foo", 1, u'baz')
            self.assertEquals(up.karma, 5)

            # Ensure the masher set the autokarma once the push is done
            self.assertEquals(up.locked, False)
            self.assertEquals(up.request, UpdateRequest.batched)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_timestamps(self, publish, *args):
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
        self.assertEquals(len(publish.call_args_list), 4)
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
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsolete_older_updates(self, publish, *args):
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
            self.assertEquals(up.status, UpdateStatus.obsolete)
            self.assertEquals(up.request, None)

            # The latest update should be in testing
            up = session.query(Update).filter_by(title=otherbuild).one()
            self.assertEquals(up.status, UpdateStatus.testing)
            self.assertEquals(up.request, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.log.exception')
    @mock.patch('bodhi.server.models.BuildrootOverride.expire', side_effect=Exception())
    def test_expire_buildroot_overrides_exception(self, expire, exception_log, publish, *args):
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

    def _ensure_three_mashes_in_same_batch(self):
        """
        Ensure there are three mashes that would go into the same batch.

        This helps us to test the max_concurrent_mashes setting.
        """
        with self.db_factory() as db:
            up = db.query(Update).one()
            user = db.query(User).first()
            # Create two more releases.
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
                status=UpdateStatus.pending,
                request=UpdateRequest.testing,
                notes=u'Useful details!', release=release,
                test_gating_status=TestGatingStatus.passed)
            update.type = UpdateType.enhancement
            db.add(update)
            release = Release(
                name=u'F27', long_name=u'Fedora 27',
                id_prefix=u'FEDORA', version=u'27',
                dist_tag=u'f27', stable_tag=u'f27-updates',
                testing_tag=u'f27-updates-testing',
                candidate_tag=u'f27-updates-candidate',
                pending_signing_tag=u'f27-updates-testing-signing',
                pending_testing_tag=u'f27-updates-testing-pending',
                pending_stable_tag=u'f27-updates-pending',
                override_tag=u'f27-override',
                state=ReleaseState.current,
                branch=u'f27')
            db.add(release)
            build = RpmBuild(nvr=u'bodhi-2.0-1.fc27', release=release, package=up.builds[0].package,
                             signed=True)
            db.add(build)
            update = Update(
                title=u'bodhi-2.0-1.fc27',
                builds=[build], user=user,
                status=UpdateStatus.pending,
                request=UpdateRequest.testing,
                notes=u'Useful details!', release=release,
                test_gating_status=TestGatingStatus.passed)
            update.type = UpdateType.enhancement
            db.add(update)
            # Wipe out the tag cache so it picks up our new releases
            Release._tag_cache = None

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_work_max_concurrent_mashes_1(self, publish, *args):
        """Assert that we don't launch more than 1 max_concurrent_mashes."""
        self._ensure_three_mashes_in_same_batch()
        self.masher.log.info = mock.MagicMock()

        with mock.patch.dict(config, {'max_concurrent_mashes': 1}):
            self.masher.work(self._make_msg())

        info_log_messages = [c[1] for c in self.masher.log.info.mock_calls]
        waiting_messages = [m for m in info_log_messages if 'Waiting on' in m[0]]
        # Since we have max_concurrent_mashes set to 1 and there are 3 mashes to be done, we should
        # see two log messages that say it's waiting on 1 mash to finish.
        self.assertEqual(waiting_messages, [('Waiting on %d mashes for priority %s', 1, 0),
                                            ('Waiting on %d mashes for priority %s', 1, 0)])

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_work_max_concurrent_mashes_2(self, publish, *args):
        """Assert that we don't launch more than 2 max_concurrent_mashes."""
        self._ensure_three_mashes_in_same_batch()
        self.masher.log.info = mock.MagicMock()

        with mock.patch.dict(config, {'max_concurrent_mashes': 2}):
            self.masher.work(self._make_msg())

        info_log_messages = [c[1] for c in self.masher.log.info.mock_calls]
        waiting_messages = [m for m in info_log_messages if 'Waiting on' in m[0]]
        # Since we have max_concurrent_mashes set to 2 and there are 3 mashes to be done, we should
        # see one log message that says we are waiting on the first two to finish.
        self.assertEqual(waiting_messages, [('Waiting on %d mashes for priority %s', 2, 0)])


class MasherThreadBaseTestCase(base.BaseTestCase):
    """
    This test class has common setUp() and tearDown() methods that are useful for testing the
    MasherThread class.
    """
    def setUp(self):
        """
        Set up the test conditions.
        """
        super(MasherThreadBaseTestCase, self).setUp()
        buildsys.setup_buildsystem({'buildsystem': 'dev'})
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        """
        Clean up after the tests.
        """
        super(MasherThreadBaseTestCase, self).tearDown()
        shutil.rmtree(self.tempdir)
        buildsys.teardown_buildsystem()

    def _make_msg(self, extra_push_args=None):
        """
        Use bodhi-push to start a compose, and return the fedmsg that bodhi-push sends.

        Returns:
            dict: A dictionary of the fedmsg that bodhi-push sends.
        """
        return _make_msg(base.TransactionalSessionMaker(self.Session), extra_push_args)


class TestMasherThread__get_master_repomd_url(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread._get_master_repomd_url() method."""
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
        t = MasherThread(msg['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        url = t._get_master_repomd_url('aarch64')

        self.assertEqual(
            url,
            'http://example.com/pub/fedora-secondary/updates/testing/17/aarch64/repodata.repomd.xml'
        )

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
        t = MasherThread(msg['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        with self.assertRaises(ValueError) as exc:
            t._get_master_repomd_url('aarch64')

        self.assertEqual(six.text_type(exc.exception),
                         'Could not find fedora_testing_alt_master_repomd in the config file')

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
        t = MasherThread(msg['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        url = t._get_master_repomd_url('x86_64')

        self.assertEqual(
            url,
            'http://example.com/pub/fedora/linux/updates/testing/17/x86_64/repodata.repomd.xml'
        )

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
        t = MasherThread(msg['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])

        url = t._get_master_repomd_url('aarch64')

        self.assertEqual(
            url,
            'http://example.com/pub/fedora/linux/updates/testing/17/aarch64/repodata.repomd.xml'
        )


class TestMasherThread__perform_tag_actions(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread._perform_tag_actions() method."""
    @mock.patch('bodhi.server.consumers.masher.buildsys.wait_for_tasks')
    def test_with_failed_tasks(self, wait_for_tasks):
        """
        Assert that the method raises an Exception when the buildsys gives us failed tasks.
        """
        wait_for_tasks.return_value = ['failed_task_1']
        msg = self._make_msg()
        t = MasherThread(msg['body']['msg']['composes'][0],
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


class TestMasherThread_check_all_karma_thresholds(MasherThreadBaseTestCase):
    """Test the MasherThread.check_all_karma_thresholds() method."""
    @mock.patch('bodhi.server.models.Update.check_karma_thresholds',
                mock.MagicMock(side_effect=exceptions.BodhiException('BOOM')))
    def test_BodhiException(self):
        """Assert that a raised BodhiException gets caught and logged."""
        msg = self._make_msg()
        t = MasherThread(msg['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = Compose.from_dict(self.db, msg['body']['msg']['composes'][0])
        t.db = self.db
        t.log.exception = mock.MagicMock()

        t.check_all_karma_thresholds()

        t.log.exception.assert_called_once_with('Problem checking karma thresholds')


class TestMasherThread_eject_from_mash(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread.eject_from_mash() method."""
    @mock.patch('bodhi.server.notifications.publish')
    def test_testing_request(self, publish):
        """
        Assert correct behavior when the update's request is set to testing.
        """
        up = self.db.query(Update).one()
        up.request = UpdateRequest.testing
        self.db.commit()
        msg = self._make_msg()
        t = MasherThread(msg['body']['msg']['composes'][0],
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


class TestMasherThread_init_state(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread.init_state() method."""
    def test_creates_mash_dir(self):
        """Assert that mash_dir gets created if it doesn't exist."""
        mash_dir = os.path.join(self.tempdir, 'cool_dir')
        msg = self._make_msg()
        t = MasherThread(msg['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, mash_dir)
        # t.work() would normally set this up for us, so we'll just fake it
        t.id = getattr(self.db.query(Release).one(), '{}_tag'.format('stable'))

        t.init_state()

        self.assertTrue(os.path.exists(mash_dir))


class TestMasherThread_load_state(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread.load_state() method."""
    def test_with_completed_repo(self):
        """Test when there is a completed_repo in the checkpoints."""
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = self.db.query(Compose).one()
        t.compose.checkpoints = json.dumps({'other': 'checkpoint', 'completed_repo': '/path/to/it'})
        t.db = self.db

        t.load_state()

        self.assertEqual(t._checkpoints, {'other': 'checkpoint', 'completed_repo': '/path/to/it'})
        self.assertEqual(t.path, '/path/to/it')

    def test_without_completed_repo(self):
        """Test when there is not a completed_repo in the checkpoints."""
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t._checkpoints = {'cool': 'checkpoint'}
        t.compose = self.db.query(Compose).one()
        t.compose.checkpoints = json.dumps({'other': 'checkpoint'})
        t.db = self.db

        t.load_state()

        self.assertEqual(t._checkpoints, {'other': 'checkpoint'})
        self.assertEqual(t.path, None)


class TestMasherThread_remove_state(MasherThreadBaseTestCase):
    """Test the remove_state() method."""
    def test_remove_state(self):
        """Assert that remove_state() deletes the Compose."""
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.db = self.db

        t.remove_state()

        self.db.flush()
        self.assertEqual(self.db.query(Compose).count(), 0)


class TestMasherThread_save_state(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread.save_state() method."""
    def test_with_state(self):
        """Test the optional state parameter."""
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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


class TestMasherThread_wait_for_sync(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread.wait_for_sync() method."""
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
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        t.wait_for_sync()

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
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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
            t.wait_for_sync()
            assert False, "Compose with just source passed"
        except Exception as ex:
            assert str(ex) == "Not found an arch to wait_for_sync with"

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
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, 'compose', 'Everything', arch, 'os', 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        t.wait_for_sync()

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

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml'})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep')
    @mock.patch(
        'bodhi.server.consumers.masher.urllib2.urlopen',
        side_effect=[urllib2.HTTPError('url', 404, 'Not found', {}, None),
                     StringIO('---\nyaml: rules')])
    def test_httperror(self, urlopen, sleep, publish):
        """
        Assert that an HTTPError is properly caught and logged, and that the algorithm continues.
        """
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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

        t.wait_for_sync()

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
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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
            t.wait_for_sync()

        self.assertEqual(six.text_type(exc.exception),
                         'Could not find fedora_testing_master_repomd in the config file')
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
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()
        t.id = 'f26-updates-testing'
        t.log = mock.MagicMock()
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        repodata = os.path.join(t.path, 'compose', 'Everything', 'x86_64', 'os', 'repodata')
        os.makedirs(repodata)

        t.wait_for_sync()

        publish.assert_called_once_with(topic='mashtask.sync.wait',
                                        msg={'repo': t.id, 'agent': 'bowlofeggs'}, force=True)
        t.log.error.assert_called_once_with(
            'Cannot find local repomd: %s', os.path.join(repodata, 'repomd.xml'))

    @mock.patch.dict(
        'bodhi.server.consumers.masher.config',
        {'fedora_testing_master_repomd':
            'http://example.com/pub/fedora/linux/updates/testing/%s/%s/repodata.repomd.xml'})
    @mock.patch('bodhi.server.consumers.masher.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.time.sleep')
    @mock.patch(
        'bodhi.server.consumers.masher.urllib2.urlopen',
        side_effect=[urllib2.URLError('it broke'),
                     StringIO('---\nyaml: rules')])
    def test_urlerror(self, urlopen, sleep, publish):
        """
        Assert that a URLError is properly caught and logged, and that the algorithm continues.
        """
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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

        t.wait_for_sync()

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


class TestMasherThread__mark_status_changes(MasherThreadBaseTestCase):
    """Test the _mark_status_changes() method."""
    def test_stable_update(self):
        """Assert that a stable update gets the right status."""
        update = Update.query.one()
        update.status = UpdateStatus.testing
        update.request = UpdateRequest.stable
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
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


class TestMasherThread__unlock_updates(MasherThreadBaseTestCase):
    """Test the _unlock_updates() method."""
    def test__unlock_updates(self):
        """Assert that _unlock_updates() works correctly."""
        update = Update.query.one()
        update.request = UpdateRequest.testing
        t = MasherThread(self._make_msg()['body']['msg']['composes'][0],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.compose = self.db.query(Compose).one()

        t._unlock_updates()

        update = Update.query.one()
        self.assertIsNone(update.request)
        self.assertFalse(update.locked)
