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
import json
import os
import shutil
import tempfile
import time
import unittest
import urllib2
import urlparse
import pytest
import re

import mock

from bodhi.server import buildsys, log, initialize_db
from bodhi.server.config import config
from bodhi.server.consumers.masher import Masher, MasherThread, PungiMashThread, PungiMasherThread
from bodhi.server.models import (
    Base, Build, BuildrootOverride, Release, ReleaseState, RpmBuild, TestGatingStatus, Update,
    UpdateRequest, UpdateStatus, UpdateType, User, ModuleBuild, ModulePackage)
from bodhi.server.util import mkmetadatadir, transactional_session_maker
from bodhi.tests.server import base, populate


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


def makemsg(body=None):
    if not body:
        body = {'updates': [u'bodhi-2.0-1.fc17'], 'agent': u'lmacken'}
    return {
        'topic': u'org.fedoraproject.dev.bodhi.masher.start',
        'body': {
            u'i': 1,
            u'msg': body,
            u'msg_id': u'2014-9568c910-91de-4870-90f5-709cc577d56d',
            u'timestamp': 1401728063,
            u'topic': u'org.fedoraproject.dev.bodhi.masher.start',
            u'username': u'lmacken',
        },
    }


class TestMasher(unittest.TestCase):

    def setUp(self):
        self._new_mash_stage_dir = tempfile.mkdtemp()

        test_config = base.original_config.copy()
        test_config['mash_stage_dir'] = self._new_mash_stage_dir
        test_config['mash_dir'] = os.path.join(self._new_mash_stage_dir, 'mash')

        mock_config = mock.patch.dict(
            'bodhi.server.consumers.masher.config', test_config)
        mock_config.start()
        self.addCleanup(mock_config.stop)

        os.makedirs(os.path.join(self._new_mash_stage_dir, 'mash'))

        buildsys.setup_buildsystem({'buildsystem': 'dev'})

        fd, self.db_filename = tempfile.mkstemp(prefix='bodhi-testing-', suffix='.db')
        db_path = 'sqlite:///%s' % self.db_filename
        # The BUILD_ID environment variable is set by Jenkins and allows us to
        # detect if
        # we are running the tests in jenkins or not
        # Note: The URL below spans two lines.
        # https://wiki.jenkins-ci.org/display/JENKINS/Building+a+software+project
        # #Buildingasoftwareproject-below
        if os.environ.get('BUILD_ID'):
            faitout = 'http://209.132.184.152/faitout/'
            try:
                import requests
                req = requests.get('%s/new' % faitout)
                if req.status_code == 200:
                    db_path = req.text
                    print('Using faitout at: %s' % db_path)
            except:
                pass
        engine = initialize_db({'sqlalchemy.url': db_path})
        Base.metadata.create_all(engine)
        self.db_factory = transactional_session_maker()

        with self.db_factory() as session:
            populate(session)
            assert session.query(Update).count() == 1

        self.koji = buildsys.get_session()
        self.koji.clear()  # clear out our dev introspection

        self.msg = makemsg()
        self.tempdir = tempfile.mkdtemp('bodhi')
        self.masher = Masher(FakeHub(), db_factory=self.db_factory, mash_dir=self.tempdir)

        # Reset "cached" objects before each test.
        Release._all_releases = None
        Release._tag_cache = None

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        try:
            os.remove(self.db_filename)
        except:
            pass
        buildsys.teardown_buildsystem()
        shutil.rmtree(self._new_mash_stage_dir)

    def set_stable_request(self, title):
        with self.db_factory() as session:
            query = session.query(Update).filter_by(title=title)
            update = query.one()
            update.request = UpdateRequest.stable
            session.flush()

    @mock.patch('bodhi.server.consumers.masher.bugs.set_bugtracker')
    def test___init___sets_bugtracker(self, set_bugtracker):
        """
        Assert that Masher.__init__() calls bodhi.server.bugs.set_bugtracker().
        """
        Masher(FakeHub(), db_factory=self.db_factory, mash_dir=self.tempdir)

        set_bugtracker.assert_called_once_with()

    @mock.patch('bodhi.server.notifications.publish')
    def test_invalid_signature(self, publish):
        """Make sure the masher ignores messages that aren't signed with the
        appropriate releng cert
        """
        with self.db_factory() as session:
            # Ensure that the update was locked
            up = session.query(Update).one()
            up.locked = False

        fakehub = FakeHub()
        fakehub.config['releng_fedmsg_certname'] = 'foo'
        self.masher = Masher(fakehub, db_factory=self.db_factory)
        self.masher.consume(self.msg)

        # Make sure the update did not get locked
        with self.db_factory() as session:
            # Ensure that the update was locked
            up = session.query(Update).one()
            self.assertFalse(up.locked)

        # Ensure mashtask.start never got sent
        self.assertEquals(len(publish.call_args_list), 0)

    @mock.patch('bodhi.server.notifications.publish')
    def test_push_invalid_update(self, publish):
        msg = makemsg()
        msg['body']['msg']['updates'] = u'invalidbuild-1.0-1.fc17'
        self.masher.consume(msg)
        self.assertEquals(len(publish.call_args_list), 1)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch.object(MasherThread, 'verify_updates', mock_exc)
    @mock.patch('bodhi.server.notifications.publish')
    def test_update_locking(self, publish, *args):
        with self.db_factory() as session:
            up = session.query(Update).one()
            up.locked = False

        self.masher.consume(self.msg)

        # Ensure that fedmsg was called 4 times
        self.assertEquals(len(publish.call_args_list), 3)

        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=False, repo='f17-updates-testing', agent='lmacken'),
            force=True)

        with self.db_factory() as session:
            # Ensure that the update was locked
            up = session.query(Update).one()
            self.assertTrue(up.locked)

            # Ensure we can't set a request
            from bodhi.server.exceptions import LockedUpdateException
            try:
                up.set_request(session, UpdateRequest.stable, u'bodhi')
                assert False, 'Set the request on a locked update'
            except LockedUpdateException:
                pass

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_tags(self, publish, *args):
        # Make the build a buildroot override as well
        title = self.msg['body']['msg']['updates'][0]
        with self.db_factory() as session:
            release = session.query(Update).one().release
            build = session.query(Build).one()
            nvr = build.nvr
            pending_testing_tag = release.pending_testing_tag
            override_tag = release.override_tag
            self.koji.__tagged__[title] = [release.override_tag,
                                           pending_testing_tag]

        # Start the push
        self.masher.consume(self.msg)

        # Ensure that fedmsg was called 3 times
        self.assertEquals(len(publish.call_args_list), 4)
        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=True, repo='f17-updates-testing', agent='lmacken'),
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

        self.masher.consume(self.msg)

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
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_tag_ordering(self, publish, *args):
        """
        Test pushing an batch of updates with multiple builds for the same package.
        Ensure that the latest version is tagged last.
        """
        otherbuild = u'bodhi-2.0-2.fc17'
        self.msg['body']['msg']['updates'].insert(0, otherbuild)

        with self.db_factory() as session:
            firstupdate = session.query(Update).filter_by(
                title=self.msg['body']['msg']['updates'][1]).one()
            build = RpmBuild(nvr=otherbuild, package=firstupdate.builds[0].package)
            session.add(build)
            update = Update(
                title=otherbuild, builds=[build], type=UpdateType.bugfix,
                request=UpdateRequest.testing, notes=u'second update', user=firstupdate.user,
                release=firstupdate.release)
            session.add(update)
            session.flush()

        # Start the push
        self.masher.consume(self.msg)

        # Ensure that fedmsg was called 5 times
        self.assertEquals(len(publish.call_args_list), 5)
        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=True, repo='f17-updates-testing', agent='lmacken'),
            force=True)

        # Ensure our two updates were moved
        self.assertEquals(len(self.koji.__moved__), 2)
        self.assertEquals(len(self.koji.__added__), 0)

        # Ensure the most recent version is tagged last in order to be the 'koji latest-pkg'
        self.assertEquals(self.koji.__moved__[0],
                          (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-1.fc17'))
        self.assertEquals(self.koji.__moved__[1],
                          (u'f17-updates-candidate', u'f17-updates-testing', u'bodhi-2.0-2.fc17'))

    def test_statefile(self):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)
        t.id = 'f17-updates-testing'
        t.init_state()
        t.save_state()
        self.assertTrue(os.path.exists(t.mash_lock))
        with file(t.mash_lock) as f:
            state = json.load(f)
        try:
            self.assertEquals(state, {u'updates': [u'bodhi-2.0-1.fc17'], u'completed_repos': []})
        finally:
            t.remove_state()

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.mail._send_mail')
    def test_testing_digest(self, mail, *args):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)
        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None
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

    def test_sanity_check(self):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)
        t.id = 'f17-updates-testing'
        t.init_path()

        # test without any arches
        try:
            t.sanity_check_repo()
            assert False, "Sanity check didn't fail with empty dir"
        except:
            pass

        # test with valid repodata
        for arch in ('i386', 'x86_64', 'armhfp'):
            repo = os.path.join(t.path, t.id, arch)
            os.makedirs(repo)
            mkmetadatadir(repo)

        t.sanity_check_repo()

        # test with truncated/busted repodata
        xml = os.path.join(t.path, t.id, 'i386', 'repodata', 'repomd.xml')
        repomd = open(xml).read()
        with open(xml, 'w') as f:
            f.write(repomd[:-10])

        from bodhi.server.exceptions import RepodataException
        try:
            t.sanity_check_repo()
            assert False, 'Busted metadata passed'
        except RepodataException:
            pass

    def test_stage(self):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)
        t.id = 'f17-updates-testing'
        t.init_path()
        t.stage_repo()
        stage_dir = config.get('mash_stage_dir')
        link = os.path.join(stage_dir, t.id)
        self.assertTrue(os.path.islink(link))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
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
                branch=u'f18')
            db.add(release)
            build = RpmBuild(nvr=u'bodhi-2.0-1.fc18', release=release, package=up.builds[0].package)
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

        self.msg['body']['msg']['updates'] += [u'bodhi-2.0-1.fc18']

        self.masher.consume(self.msg)

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
                 'updates': [u'bodhi-2.0-1.fc18'],
                 'agent': 'lmacken'},
            topic='mashtask.mashing'))
        self.assertEquals(calls[4], mock.call(
            force=True,
            msg={'success': True, 'repo': 'f18-updates', 'agent': 'lmacken'},
            topic='mashtask.complete'))
        self.assertEquals(calls[5], mock.call(
            force=True,
            msg={'repo': u'f17-updates-testing',
                 'updates': [u'bodhi-2.0-1.fc17'],
                 'agent': 'lmacken'},
            topic='mashtask.mashing'))
        self.assertEquals(calls[-1], mock.call(
            force=True,
            msg={'success': True,
                 'repo': 'f17-updates-testing',
                 'agent': 'lmacken'},
            topic='mashtask.complete'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
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
                branch=u'f18')
            db.add(release)
            build = RpmBuild(nvr=u'bodhi-2.0-1.fc18', release=release, package=up.builds[0].package)
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

        self.msg['body']['msg']['updates'] += [u'bodhi-2.0-1.fc18']

        self.masher.consume(self.msg)

        # Ensure that F17 updates-testing runs before F18
        calls = publish.mock_calls
        self.assertEquals(calls[1], mock.call(
            msg={'repo': u'f17-updates-testing',
                 'updates': [u'bodhi-2.0-1.fc17'],
                 'agent': 'lmacken'},
            force=True,
            topic='mashtask.mashing'))
        self.assertEquals(calls[3], mock.call(
            msg={'success': True,
                 'repo': 'f17-updates-testing',
                 'agent': 'lmacken'},
            force=True,
            topic='mashtask.complete'))
        self.assertEquals(calls[4], mock.call(
            msg={'repo': u'f18-updates',
                 'updates': [u'bodhi-2.0-1.fc18'],
                 'agent': 'lmacken'},
            force=True,
            topic='mashtask.mashing'))
        self.assertEquals(calls[-1], mock.call(
            msg={'success': True, 'repo': 'f18-updates', 'agent': 'lmacken'},
            force=True,
            topic='mashtask.complete'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
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
                branch=u'f18')
            db.add(release)
            build = RpmBuild(nvr=u'bodhi-2.0-1.fc18', release=release, package=up.builds[0].package)
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

        self.msg['body']['msg']['updates'] += [u'bodhi-2.0-1.fc18']

        self.masher.consume(self.msg)

        # Ensure that F18 and F17 run in parallel
        calls = publish.mock_calls
        if calls[1] == mock.call(
                msg={'repo': u'f18-updates', 'updates': [u'bodhi-2.0-1.fc18'], 'agent': 'lmacken'},
                force=True, topic='mashtask.mashing'):
            self.assertEquals(
                calls[2],
                mock.call(msg={'repo': u'f17-updates', 'updates': [u'bodhi-2.0-1.fc17'],
                               'agent': 'lmacken'},
                          force=True, topic='mashtask.mashing'))
        elif calls[1] == self.assertEquals(
                calls[1],
                mock.call(
                    msg={'repo': u'f17-updates', 'updates': [u'bodhi-2.0-1.fc17'],
                         'agent': 'lmacken'},
                    force=True, topic='mashtask.mashing')):
            self.assertEquals(
                calls[2],
                mock.call(msg={'repo': u'f18-updates', 'updates': [u'bodhi-2.0-1.fc18']},
                          force=True, topic='mashtask.mashing'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.notifications.init')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.util.cmd')
    def test_update_comps(self, cmd, *args):
        cmd.return_value = '', '', 0
        self.masher.consume(self.msg)
        self.assertIn(mock.call(['git', 'pull'], mock.ANY), cmd.mock_calls)
        self.assertIn(mock.call(['make'], mock.ANY), cmd.mock_calls)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_mash(self, cmd, publish, *args):
        cmd.return_value = '', '', 0

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')

        t = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)

        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            repo='f17-updates',
                                            agent='ralph'))
        publish.assert_any_call(topic='update.complete.stable',
                                force=True,
                                msg=mock.ANY)

        self.assertIn(mock.call(['mash'] + [mock.ANY] * 7), cmd.mock_calls)
        self.assertEquals(len(t.state['completed_repos']), 1)

    @mock.patch(**mock_failed_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_failed_gating(self, cmd, publish, *args):
        cmd.return_value = '', '', 0

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')

        t = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)

        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            repo='f17-updates',
                                            agent='ralph'))
        publish.assert_any_call(topic='update.eject', msg=mock.ANY, force=True)

        self.assertIn(mock.call(['mash'] + [mock.ANY] * 7), cmd.mock_calls)
        self.assertEquals(len(t.state['completed_repos']), 1)

    @mock.patch(**mock_absent_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_absent_gating(self, cmd, publish, *args):
        cmd.return_value = '', '', 0

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request(u'bodhi-2.0-1.fc17')

        t = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)

        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            repo='f17-updates',
                                            agent='ralph'))
        publish.assert_any_call(topic='update.eject', msg=mock.ANY, force=True)

        self.assertIn(mock.call(['mash'] + [mock.ANY] * 7), cmd.mock_calls)
        self.assertEquals(len(t.state['completed_repos']), 1)

    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
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
        self.masher.consume(self.msg)

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
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    @mock.patch('bodhi.server.bugs.bugtracker.comment')
    @mock.patch('bodhi.server.bugs.bugtracker.close')
    def test_modify_stable_bugs(self, close, comment, *args):
        self.set_stable_request(u'bodhi-2.0-1.fc17')
        t = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)
        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None
        close.assert_called_with(
            12345,
            versions=dict(bodhi=u'bodhi-2.0-1.fc17'),
            comment=(u'bodhi-2.0-1.fc17 has been pushed to the Fedora 17 stable repository. If '
                     u'problems still persist, please make note of it in this bug report.'))

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_status_comment_testing(self, *args):
        title = self.msg['body']['msg']['updates'][0]
        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            self.assertEquals(len(up.comments), 2)

        self.masher.consume(self.msg)

        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            self.assertEquals(len(up.comments), 3)
            self.assertEquals(up.comments[-1]['text'], u'This update has been pushed to testing.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_status_comment_stable(self, *args):
        title = self.msg['body']['msg']['updates'][0]
        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            up.request = UpdateRequest.stable
            self.assertEquals(len(up.comments), 2)

        self.masher.consume(self.msg)

        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            self.assertEquals(len(up.comments), 3)
            self.assertEquals(up.comments[-1]['text'], u'This update has been pushed to stable.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_get_security_updates(self, *args):
        build = u'bodhi-2.0-1.fc17'
        t = MasherThread(u'F17', u'testing', [build],
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
            self.assertEquals(updates[0].title, build)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_unlock_updates(self, *args):
        title = self.msg['body']['msg']['updates'][0]
        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            up.request = UpdateRequest.stable
            self.assertEquals(len(up.comments), 2)

        self.masher.consume(self.msg)

        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            self.assertEquals(up.locked, False)
            self.assertEquals(up.status, UpdateStatus.stable)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.util.cmd')
    def test_resume_push(self, *args):
        title = self.msg['body']['msg']['updates'][0]
        with mock.patch.object(MasherThread, 'generate_testing_digest', mock_exc):
            with self.db_factory() as session:
                up = session.query(Update).filter_by(title=title).one()
                up.request = UpdateRequest.testing
                up.status = UpdateStatus.pending

            # Simulate a failed push
            self.masher.consume(self.msg)

        # Ensure that the update hasn't changed state
        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            self.assertEquals(up.request, UpdateRequest.testing)
            self.assertEquals(up.status, UpdateStatus.pending)

        # Resume the push
        self.msg['body']['msg']['resume'] = True
        self.masher.consume(self.msg)

        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            self.assertEquals(up.status, UpdateStatus.testing)
            self.assertEquals(up.request, None)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
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
        title = self.msg['body']['msg']['updates'][0]

        # Simulate a failed push
        with mock.patch.object(MasherThread, 'verify_updates', mock_exc):
            with self.db_factory() as session:
                up = session.query(Update).filter_by(title=title).one()
                up.request = UpdateRequest.testing
                up.status = UpdateStatus.pending
                self.assertEquals(up.stable_karma, 3)
            self.masher.consume(self.msg)

        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()

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
        self.msg['body']['msg']['resume'] = True
        self.masher.consume(self.msg)

        with self.db_factory() as session:
            up = session.query(Update).filter_by(title=title).one()
            up.comment(session, u"foo", 1, u'baz')
            self.assertEquals(up.karma, 5)

            # Ensure the masher set the autokarma once the push is done
            self.assertEquals(up.locked, False)
            self.assertEquals(up.request, UpdateRequest.batched)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_push_timestamps(self, publish, *args):
        title = self.msg['body']['msg']['updates'][0]
        with self.db_factory() as session:
            release = session.query(Update).one().release
            pending_testing_tag = release.pending_testing_tag
            self.koji.__tagged__[title] = [release.override_tag,
                                           pending_testing_tag]

        # Start the push
        self.masher.consume(self.msg)

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
            msg=dict(success=True, repo='f17-updates-testing', agent='lmacken'))

        self.koji.clear()

        self.masher.consume(self.msg)

        with self.db_factory() as session:
            # Check that the request_complete method got run
            up = session.query(Update).one()
            self.assertIsNone(up.request)
            self.assertIsNotNone(up.date_stable)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.server.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.server.consumers.masher.MashThread.run')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.server.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.server.notifications.publish')
    def test_obsolete_older_updates(self, publish, *args):
        otherbuild = u'bodhi-2.0-2.fc17'
        oldbuild = None
        self.msg['body']['msg']['updates'].insert(0, otherbuild)

        with self.db_factory() as session:
            # Put the older update into testing
            oldupdate = session.query(Update).one()
            oldbuild = oldupdate.builds[0].nvr
            oldupdate.status = UpdateStatus.testing
            oldupdate.request = None
            oldupdate.locked = False

            # Create a newer build
            build = RpmBuild(nvr=otherbuild, package=oldupdate.builds[0].package)
            session.add(build)
            update = Update(
                title=otherbuild, builds=[build], type=UpdateType.bugfix,
                request=UpdateRequest.testing, notes=u'second update', user=oldupdate.user,
                release=oldupdate.release)
            session.add(update)
            session.flush()

        self.masher.consume(self.msg)

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
    @mock.patch('bodhi.server.consumers.masher.PungiMashThread.run')
    @mock.patch('bodhi.server.consumers.masher.PungiMasherThread.wait_for_mash')
    @mock.patch('bodhi.server.consumers.masher.PungiMasherThread.sanity_check_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiMasherThread.stage_repo')
    @mock.patch('bodhi.server.consumers.masher.PungiMasherThread.wait_for_sync')
    @mock.patch('bodhi.server.buildsys.DevBuildsys.listTagged')
    @mock.patch('bodhi.server.buildsys.DevBuildsys.listBuildRPMs')
    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.PungiMasherThread._get_compose_dir')
    def test_mash_modules(self, get_compose_dir, publish, listbuildrpms, listtagged,
                          wait_for_sync, stage_repo, sanity_check_repo, wait_for_mash,
                          run, *args):
        with self.db_factory() as db:
            user = db.query(User).first()

            # Create test data needed to test mashing modules
            # This release is here only as a placeholder, as for now the modules
            # cant be found under a release tag in koji.
            release = Release(
                name=u'F27-modular', long_name=u'Fedora 27 modular',
                id_prefix=u'FEDORA', version=u'27',
                dist_tag=u'f27-modular', stable_tag=u'f27-modular-updates',
                testing_tag=u'f27-modular-updates-testing',
                candidate_tag=u'f27-modular-updates-candidate',
                pending_signing_tag=u'f27-modular-updates-testing-signing',
                pending_testing_tag=u'f27-modular-updates-testing-pending',
                pending_stable_tag=u'f27-modular-updates-pending',
                override_tag=u'f27-modular-override',
                branch=u'f27-modular')
            db.add(release)
            package1 = ModulePackage(name=u"platform")
            package2 = ModulePackage(name=u"host")
            package3 = ModulePackage(name=u"shim")
            package4 = ModulePackage(name=u"installer")
            db.add(package1)
            db.add(package2)
            db.add(package3)
            db.add(package4)
            build1 = ModuleBuild(
                nvr=u'platform-master-20170818100407', release=release, package=package1)
            db.add(build1)
            build2 = ModuleBuild(
                nvr=u'host-master-20170830200108', release=release, package=package2)
            db.add(build2)
            build3 = ModuleBuild(
                nvr=u'shim-master-20170502110601', release=release, package=package3)
            db.add(build3)
            build4 = ModuleBuild(
                nvr=u'installer-master-20170822180922', release=release, package=package4)
            db.add(build4)
            update1 = Update(
                title=u'platform-master-20170818100407',
                builds=[build1], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release)
            update1.type = UpdateType.enhancement
            update1.assign_alias()
            db.add(update1)
            update2 = Update(
                title=u'host-master-20170830200108',
                builds=[build2], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release)
            update2.type = UpdateType.enhancement
            update2.assign_alias()
            db.add(update2)
            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        msg = makemsg(
            body={'updates': [
                u'platform-master-20170818100407',
                u'host-master-20170830200108'], 'agent': u'mcurlej'}
        )

        template_build = {
            'build_id': 16058,
            'completion_time': '2007-08-24 23:26:10.890319',
            'completion_ts': 1187997970,
            'creation_event_id': 151517,
            'creation_time': '2007-08-24 19:38:29.422344',
            'epoch': None,
            'extra': None,
            'id': 16058,
            'name': 'TurboGears',
            'nvr': 'TurboGears-1.0.2.2-2.fc17',
            'owner_id': 388,
            'owner_name': 'lmacken',
            'package_id': 8,
            'package_name': 'TurboGears',
            'release': '2.fc17',
            'state': 1,
            'tag_id': 19,
            'tag_name': 'f17-updates-candidate',
            'task_id': 127621,
            'version': '1.0.2.2'
        }

        rpms = [
            {
                'arch': 'src',
                'build_id': 6475,
                'buildroot_id': 1883,
                'buildtime': 1178868422,
                'epoch': 1,
                'id': 62330,
                'name': 'TurboGears',
                'nvr': 'TurboGears-1.0.2.2-2.fc17',
                'payloadhash': '6787febe92434a9be2a8f309d0e2014e',
                'release': '2.fc17',
                'size': 761742,
                'version': '1.0.2.2'
            },
            {
                'arch': 'noarch',
                'build_id': 6475,
                'buildroot_id': 1883,
                'buildtime': 1178868537,
                'epoch': 1,
                'id': 62331,
                'name': 'TurboGears',
                'nvr': 'TurboGears-1.0.2.2-2.fc17',
                'payloadhash': 'f3ec9bdce453816f94283a15a47cb952',
                'release': '2.fc17',
                'size': 1993385,
                'version': '1.0.2.2'
            }
        ]

        builds_md = []
        for i, build in enumerate(msg["body"]["msg"]["updates"]):
            nsv_list = build.split("-")
            build_name = nsv_list[0]
            build_version = nsv_list[2]
            prot_build = template_build.copy()
            prot_build["build_id"] += i
            prot_build["creation_event_id"] += i
            prot_build["nvr"] = build
            prot_build["id"] += i
            prot_build["name"] = build_name
            prot_build["package_id"] += i
            prot_build["package_name"] = build_name
            prot_build["release"] = "f27"
            prot_build["tag_name"] = "f27-modular-updates"
            prot_build["task_id"] += i
            prot_build["version"] = build_version
            builds_md.append(prot_build)

        listtagged.return_value = builds_md
        listbuildrpms.return_value = rpms

        # mock config option which will have a test pungi config
        bodhi_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
        pungi_conf_path = os.path.join(bodhi_dir, "devel", "pungi", "fedora-modular-example.conf")
        mock_config = config.copy()
        mock_config["pungi_modular_config_path"] = pungi_conf_path

        # to test updateinfo.xml we need a dir structure as the actual repo.
        compose_dir = os.path.join(self.tempdir, "compose_dir")
        os.mkdir(compose_dir)
        os.mkdir(os.path.join(self.tempdir, "compose_dir", "x86_64"))
        os.mkdir(os.path.join(self.tempdir, "compose_dir", "x86_64", "os"))
        repodata_dir = os.path.join(self.tempdir, "compose_dir", "x86_64", "os", "repodata")
        os.mkdir(repodata_dir)

        get_compose_dir.return_value = compose_dir
        # we need a mocked repomd.xml in the repo structure
        mock_repomd = (u'<?xml version="1.0" encoding="UTF-8"?>'
                       u'<repomd xmlns="http://linux.duke.edu/metadata/repo" '
                       u'xmlns:rpm="http://linux.duke.edu/metadata/rpm"></repomd>')
        repomd_file = os.path.join(repodata_dir, "repomd.xml")
        with open(repomd_file, "w+") as fd:
            fd.write(mock_repomd)
        with mock.patch.dict("bodhi.server.consumers.masher.config", mock_config):
            self.masher.consume(msg)

        publish.assert_called_with(topic="mashtask.complete",
                                   force=True,
                                   msg=dict(success=True,
                                            repo='f27-modular-updates',
                                            agent='mcurlej'))
        wait_for_sync.assert_called_once()
        run.assert_called_once()
        stage_repo.assert_called_once()
        sanity_check_repo.assert_called_once()
        wait_for_mash.assert_called_once()

        # open and check if our repomd.xml was updated by updateinfo.xml
        with open(repomd_file, "r") as fd:
            updated_repomd = fd.read()

        assert '<data type="updateinfo">' in updated_repomd
        assert '-updateinfo.xml.xz' in updated_repomd
        # get the name of updateinfo.xml.xz from repomd.xml and check if it
        # exits
        rx = re.compile('[\w]+\-updateinfo\.xml\.xz')
        updateinfo = rx.search(updated_repomd).group()
        updateinfo_path = os.path.join(repodata_dir, updateinfo)

        assert os.path.isfile(updateinfo_path)



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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)

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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)

        with self.assertRaises(ValueError) as exc:
            t._get_master_repomd_url('aarch64')

        self.assertEqual(unicode(exc.exception),
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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)

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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)

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
        t = MasherThread(u'F26', u'stable', [u'bodhi-2.3.2-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.move_tags_async.append(
            (u'f26-updates-candidate', u'f26-updates-testing', u'bodhi-2.3.2-1.fc26'))

        with self.assertRaises(Exception) as exc:
            t._perform_tag_actions()

        self.assertEqual(unicode(exc.exception), "Failed to move builds: ['failed_task_1']")
        # Since the task didn't really fail (we just mocked that it did) the DevBuildsys should have
        # registered that the move occurred.
        self.assertEqual(buildsys.DevBuildsys.__moved__,
                         [('f26-updates-candidate', 'f26-updates-testing', 'bodhi-2.3.2-1.fc26')])


class TestMasherThread_eject_from_mash(MasherThreadBaseTestCase):
    """This test class contains tests for the MasherThread.eject_from_mash() method."""
    @mock.patch('bodhi.server.notifications.publish')
    def test_testing_request(self, publish):
        """
        Assert correct behavior when the update's request is set to testing.
        """
        up = self.db.query(Update).one()
        up.request = UpdateRequest.testing
        t = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.db = self.Session()
        # t.work() would normally set this up for us, so we'll just fake it
        t.id = getattr(self.db.query(Release).one(), '{}_tag'.format('stable'))
        t.updates = set([up])

        t.eject_from_mash(up, 'This update is unacceptable!')

        self.assertEqual(buildsys.DevBuildsys.__untag__,
                         [(u'f17-updates-testing-pending', u'bodhi-2.0-1.fc17')])
        publish.assert_called_once_with(
            topic='update.eject',
            msg={'repo': 'f17-updates', 'update': up,
                 'reason': 'This update is unacceptable!', 'request': UpdateRequest.stable,
                 'release': 'F17', 'agent': 'bowlofeggs'},
            force=True)
        # The update should have been removed from t.updates
        self.assertEqual(t.updates, set([]))
        # The update's title should also have been removed from t.state['updates']
        self.assertEqual(t.state['updates'], [])


class TestMasherThread_my_comps_dir(unittest.TestCase):
    """This test class contains tests for the MasherThread.my_comps_dir() method."""
    @mock.patch('bodhi.server.consumers.masher.config', {'comps_dir': '/some/path'})
    def test_my_comps_dir(self):
        """Assert correct return value from the my_comps_dir property."""
        self.masher_thread = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                                          u'bowlofeggs', mock.Mock(), mock.Mock(), mock.Mock())
        self.masher_thread.id = 'f17-updates'

        self.assertEqual(self.masher_thread.my_comps_dir, '/some/path/f17-updates')


class TestMasherThread_update_comps(unittest.TestCase):
    """This test class contains tests for the MasherThread.update_comps() method."""

    def setUp(self):
        self.masher_thread = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                                          u'bowlofeggs', mock.Mock(), mock.Mock(), mock.Mock())
        self.masher_thread.id = 'f17-updates'

    @mock.patch('bodhi.server.consumers.masher.os.path.exists')
    @mock.patch('bodhi.server.consumers.masher.config', {'comps_dir': '/some/path',
                                                         'comps_url': 'https://example.com/'})
    @mock.patch('bodhi.server.consumers.masher.util.cmd')
    def test_comps_no_dir(self, mock_cmd, mock_exists):
        mock_exists.return_value = False
        calls = [
            mock.call(['git', 'clone', 'https://example.com/', '/some/path/f17-updates'],
                      '/some/path'),
            mock.call(['git', 'pull'], '/some/path/f17-updates'),
            mock.call(['make'], '/some/path/f17-updates'),
        ]
        self.masher_thread.update_comps()
        self.assertEqual(calls, mock_cmd.call_args_list)
        mock_exists.assert_called_once_with('/some/path/f17-updates')

    @mock.patch('bodhi.server.consumers.masher.os.path.exists')
    @mock.patch('bodhi.server.consumers.masher.config', {'comps_dir': '/some/path',
                                                         'comps_url': 'https://example.com/'})
    @mock.patch('bodhi.server.consumers.masher.util.cmd')
    def test_comps_existing_dir(self, mock_cmd, mock_exists):
        mock_exists.return_value = True
        calls = [
            mock.call(['git', 'pull'], '/some/path/f17-updates'),
            mock.call(['make'], '/some/path/f17-updates'),
        ]
        self.masher_thread.update_comps()
        self.assertEqual(calls, mock_cmd.call_args_list)
        mock_exists.assert_called_once_with('/some/path/f17-updates')


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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, t.id, arch, 'repodata')
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
    @mock.patch('bodhi.server.consumers.masher.time.sleep')
    @mock.patch(
        'bodhi.server.consumers.masher.urllib2.urlopen',
        side_effect=[StringIO('wrong'), StringIO('nope'), StringIO('---\nyaml: rules')])
    def test_checksum_match_third_try(self, urlopen, sleep, publish):
        """
        Assert correct operation when the repomd checksum matches on the third try.
        """
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, t.id, arch, 'repodata')
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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.id = 'f26-updates-testing'
        t.log = mock.MagicMock()
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, t.id, arch, 'repodata')
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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.id = 'f26-updates-testing'
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, t.id, arch, 'repodata')
            os.makedirs(repodata)
            with open(os.path.join(repodata, 'repomd.xml'), 'w') as repomd:
                repomd.write('---\nyaml: rules')

        with self.assertRaises(ValueError) as exc:
            t.wait_for_sync()

        self.assertEqual(unicode(exc.exception),
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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.id = 'f26-updates-testing'
        t.log = mock.MagicMock()
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        repodata = os.path.join(t.path, t.id, 'x86_64', 'repodata')
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
        release = self.db.query(Release).filter_by(name=u'F17').one()
        t = MasherThread(release, u'testing', [u'bodhi-2.4.0-1.fc26'],
                         'bowlofeggs', log, self.Session, self.tempdir)
        t.id = 'f26-updates-testing'
        t.log = mock.MagicMock()
        t.path = os.path.join(self.tempdir, t.id + '-' + time.strftime("%y%m%d.%H%M"))
        for arch in ['aarch64', 'x86_64']:
            repodata = os.path.join(t.path, t.id, arch, 'repodata')
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


class TestPungiMashThread(object):

    @mock.patch("bodhi.server.consumers.masher.Compose")
    @mock.patch("pungi.notifier.PungiNotifier")
    @mock.patch("bodhi.server.consumers.masher.PungiWrapper")
    def test_run(self, pungi_wrapper, *args):
        compose_id = "f27-modular-updates"
        pungi_conf = mock.Mock()
        target_dir = "/tmp"
        variants_conf = mock.Mock()
        logger = mock.Mock()
        pungi_wrapper.init_compose_dir = mock.Mock()
        mash = PungiMashThread(compose_id, target_dir, pungi_conf, variants_conf, logger)

        assert not mash.success
        mash.run()
        pungi_wrapper().compose_repo.assert_called_once()
        assert mash.success

    @mock.patch("bodhi.server.consumers.masher.Compose")
    @mock.patch("pungi.notifier.PungiNotifier")
    @mock.patch("bodhi.server.consumers.masher.PungiWrapper")
    def test_run_exception(self, pungi_wrapper, *args):
        compose_id = "f27-modular-updates"
        pungi_conf = mock.Mock()
        target_dir = "/tmp"
        variants_conf = mock.Mock()
        logger = mock.Mock()
        pungi_wrapper.init_compose_dir = mock.Mock()
        mash = PungiMashThread(compose_id, target_dir, pungi_conf, variants_conf, logger)

        assert not mash.success
        pungi_wrapper().compose_repo.side_effect = Exception("Mash exception!")

        with pytest.raises(Exception):
            mash.run()
            pungi_wrapper().compose_repo.assert_called_once()

        assert not mash.success


class TestPungiMasherThread(object):

    def setup_method(self, method):
        release = "f27-modular-updates"
        request = "stable"
        updates = []
        agent = "mcurlej"
        logger = mock.Mock()
        db = mock.Mock()
        mash_dir = "/tmp"
        self.wrapper = PungiMasherThread(release, request, updates, agent, logger, db, mash_dir)
        self.wrapper.id = release
        self.wrapper.path = os.path.join(mash_dir, self.wrapper.id)
        self.wrapper.db = mock.Mock()

    @mock.patch("bodhi.server.consumers.masher.config")
    def test_get_pungi_conf_path(self, config):
        config.get.return_value = "/tmp/bodhi/pungi"
        pungi_conf_path = self.wrapper._get_pungi_conf_path()
        assert pungi_conf_path == "/tmp/bodhi/pungi/fedora-modular-example.conf"

    def test_get_compose_dir(self):
        compose_dir = self.wrapper._get_compose_dir("/tmp")
        assert compose_dir == "/tmp/compose/Server"

    @mock.patch("bodhi.server.consumers.masher.PungiMasherThread._get_compose_dir")
    @mock.patch("bodhi.server.consumers.masher.sanity_check_repodata")
    @mock.patch("os.listdir")
    def test_sanity_check_repo(self, list_dir, sanity_check_repodata, get_compose_dir):
        list_dir.return_value = ["x86_64"]
        result = self.wrapper.sanity_check_repo()
        sanity_check_repodata.assert_called_once()
        get_compose_dir.assert_called_once()
        assert result

    @mock.patch("bodhi.server.consumers.masher.PungiMasherThread._get_compose_dir")
    @mock.patch("bodhi.server.consumers.masher.sanity_check_repodata")
    @mock.patch("os.listdir")
    @mock.patch("os.path.islink")
    def test_sanity_check_repo_symlink_exception(self, islink, list_dir,
                                                 sanity_check_repodata, get_compose_dir):
        list_dir.return_value = ["package.rpm"]
        islink.return_value = True
        with pytest.raises(Exception):
            self.wrapper.sanity_check_repo()
            sanity_check_repodata.assert_called_once()
            get_compose_dir.assert_called_once()
            self.log.error.assert_called_once()

    @mock.patch("bodhi.server.consumers.masher.PungiMasherThread._get_compose_dir")
    @mock.patch("bodhi.server.consumers.masher.sanity_check_repodata")
    @mock.patch("os.listdir")
    def test_sanity_check_repo_repodata_exception(self, list_dir, sanity_check_repodata,
                                                  get_compose_dir):
        list_dir.return_value = ["x86_64"]
        sanity_check_repodata.side_effect = Exception("Repodata validation failure!")
        with pytest.raises(Exception):
            self.wrapper.sanity_check_repo()
            sanity_check_repodata.assert_called_once()
            get_compose_dir.assert_called_once()
            self.log.error.assert_called_once()

    @mock.patch("bodhi.server.consumers.masher.PungiMasherThread._get_compose_dir")
    @mock.patch("bodhi.server.consumers.masher.PungiMetadata")
    def test_generate_update_info(self, pungi_metadata, get_compose_dir):
        self.wrapper.release = mock.Mock()
        self.wrapper.release.return_value = "f27-modular-updates"
        self.wrapper.generate_updateinfo()

        pungi_metadata.assert_called_once()
        get_compose_dir.assert_called_once()

    @mock.patch('bodhi.server.notifications.publish')
    def test_skip_mash(self, *args):
        masher_mock = mock.create_autospec(self.wrapper)
        masher_mock.work = lambda: PungiMasherThread.work(masher_mock)
        masher_mock.request = UpdateRequest.from_string('stable')
        release = mock.Mock()
        release.state = ReleaseState.pending
        masher_mock.db = mock.Mock()
        masher_mock.db.query.return_value.filter_by.return_value.one.return_value = release
        masher_mock.log = mock.Mock()
        masher_mock.work()

        assert masher_mock.skip_mash is True

    @mock.patch('bodhi.server.notifications.publish')
    def test_work_exception(self, *args):
        masher_mock = mock.create_autospec(self.wrapper)
        masher_mock.work = lambda: PungiMasherThread.work(masher_mock)
        masher_mock.request = UpdateRequest.from_string('stable')
        release = mock.Mock()
        release.state = ReleaseState.current
        masher_mock.db = mock.Mock()
        masher_mock.db.query.return_value.filter_by.return_value.one.return_value = release
        masher_mock.log = mock.Mock()
        masher_mock.load_updates.side_effect = Exception("Just fail!")

        with pytest.raises(Exception):
            masher_mock.work()

        masher_mock.log.exception.assert_called_once()
        masher_mock.save_state.assert_called_once()

    @mock.patch('bodhi.server.notifications.publish')
    @mock.patch('bodhi.server.consumers.masher.config')
    def test_work_compose_atomic_trees(self, config, *args):
        masher_mock = mock.create_autospec(self.wrapper)
        masher_mock.work = lambda: PungiMasherThread.work(masher_mock)
        masher_mock.request = UpdateRequest.from_string('stable')
        release = mock.Mock()
        release.state = ReleaseState.current
        masher_mock.db = mock.Mock()
        masher_mock.db.query.return_value.filter_by.return_value.one.return_value = release
        masher_mock.log = mock.Mock()
        config.get.return_value = True
        masher_mock.work()

        masher_mock.compose_atomic_trees.assert_called_once()

    def test_skipping_completed_repo(self, *args):
        masher_mock = mock.create_autospec(self.wrapper)
        masher_mock.mash = lambda: PungiMasherThread.mash(masher_mock)
        masher_mock.request = UpdateRequest.from_string('stable')
        release = mock.Mock()
        release.state = ReleaseState.current
        masher_mock.db = mock.Mock()
        masher_mock.db.query.return_value.filter_by.return_value.one.return_value = release
        masher_mock.log = mock.Mock()
        masher_mock.state = {"completed_repos": ["/tmp/mashed_repo"]}
        masher_mock.path = "/tmp/mashed_repo"

        masher_mock.mash()

        masher_mock.log.info.assert_called_once()
