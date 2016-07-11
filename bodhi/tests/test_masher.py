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

import os
import mock
import time
import json
import shutil
import unittest
import tempfile

from sqlalchemy import create_engine

from bodhi import buildsys, log
from bodhi.config import config
from bodhi.consumers.masher import Masher, MasherThread
from bodhi.models import (Base, Update, User, Release,
                          Build, UpdateRequest, UpdateType,
                          ReleaseState, BuildrootOverride,
                          UpdateStatus)
from bodhi.tests import populate

from bodhi.util import mkmetadatadir, transactional_session_maker

mock_exc = mock.Mock()
mock_exc.side_effect = Exception


mock_taskotron_results = {
    'target': 'bodhi.util.taskotron_results',
    'return_value': [{
        "outcome": "PASSED",
        "result_data": {},
        "testcase": { "name": "rpmlint", }
    }],
}

mock_failed_taskotron_results = {
    'target': 'bodhi.util.taskotron_results',
    'return_value': [{
        "outcome": "FAILED",
        "result_data": {},
        "testcase": { "name": "rpmlint", }
    }],
}

mock_absent_taskotron_results = {
    'target': 'bodhi.util.taskotron_results',
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
        }

    def subscribe(self, *args, **kw):
        pass


def makemsg(body=None):
    if not body:
        body = {'updates': ['bodhi-2.0-1.fc17'], 'agent': 'lmacken'}
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
        fd, self.db_filename = tempfile.mkstemp(prefix='bodhi-testing-', suffix='.db')
        db_path = 'sqlite:///%s' % self.db_filename
        # The BUILD_ID environment variable is set by Jenkins and allows us to
        # detect if
        # we are running the tests in jenkins or not
        # https://wiki.jenkins-ci.org/display/JENKINS/Building+a+software+project#Buildingasoftwareproject-below
        if os.environ.get('BUILD_ID'):
            faitout = 'http://209.132.184.152/faitout/'
            try:
                import requests
                req = requests.get('%s/new' % faitout)
                if req.status_code == 200:
                    db_path = req.text
                    print 'Using faitout at: %s' % db_path
            except:
                pass
        engine = create_engine(db_path)
        Base.metadata.create_all(engine)
        self.db_factory = transactional_session_maker(engine)

        with self.db_factory() as session:
            populate(session)
            assert session.query(Update).count() == 1


        self.koji = buildsys.get_session()
        self.koji.clear()  # clear out our dev introspection

        self.msg = makemsg()
        self.tempdir = tempfile.mkdtemp('bodhi')
        self.masher = Masher(FakeHub(), db_factory=self.db_factory, mash_dir=self.tempdir)

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        try:
            os.remove(self.db_filename)
        except:
            pass

    def set_stable_request(self, title):
        with self.db_factory() as session:
            query = session.query(Update).filter_by(title=title)
            update = query.one()
            update.request = UpdateRequest.stable
            session.flush()

    @mock.patch('bodhi.notifications.publish')
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

    @mock.patch('bodhi.notifications.publish')
    def test_push_invalid_update(self, publish):
        msg = makemsg()
        msg['body']['msg']['updates'] = 'invalidbuild-1.0-1.fc17'
        self.masher.consume(msg)
        self.assertEquals(len(publish.call_args_list), 1)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch.object(MasherThread, 'verify_updates', mock_exc)
    @mock.patch('bodhi.notifications.publish')
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
            from bodhi.exceptions import LockedUpdateException
            try:
                up.set_request(session, UpdateRequest.stable, u'bodhi')
                assert False, 'Set the request on a locked update'
            except LockedUpdateException:
                pass

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
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
        self.assertEquals(self.koji.__moved__[0], (u'f17-updates-candidate',
            u'f17-updates-testing', u'bodhi-2.0-1.fc17'))

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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_tag_ordering(self, publish, *args):
        """
        Test pushing an batch of updates with multiple builds for the same package.
        Ensure that the latest version is tagged last.
        """
        otherbuild = 'bodhi-2.0-2.fc17'
        self.msg['body']['msg']['updates'].insert(0, otherbuild)

        with self.db_factory() as session:
            firstupdate = session.query(Update).filter_by(title=self.msg['body']['msg']['updates'][1]).one()
            build = Build(nvr=otherbuild, package=firstupdate.builds[0].package)
            session.add(build)
            update = Update(title=otherbuild, builds=[build], type=UpdateType.bugfix,
                    request=UpdateRequest.testing, notes=u'second update',
                    user=firstupdate.user, release=firstupdate.release)
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
        self.assertEquals(self.koji.__moved__[0], (u'f17-updates-candidate',
            u'f17-updates-testing', u'bodhi-2.0-1.fc17'))
        self.assertEquals(self.koji.__moved__[1], (u'f17-updates-candidate',
            u'f17-updates-testing', u'bodhi-2.0-2.fc17'))

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
            self.assertEquals(state, {u'updates':
                [u'bodhi-2.0-1.fc17'], u'completed_repos': []})
        finally:
            t.remove_state()

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.mail._send_mail')
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

        mail.assert_called_with(config.get('bodhi_email'), config.get('fedora_test_announce_list'), mock.ANY)
        assert len(mail.mock_calls) == 2, len(mail.mock_calls)
        body = mail.mock_calls[1][1][2]
        assert body.startswith('From: updates@fedoraproject.org\r\nTo: %s\r\nX-Bodhi: fedoraproject.org\r\nSubject: Fedora 17 updates-testing report\r\n\r\nThe following builds have been pushed to Fedora 17 updates-testing\n\n    bodhi-2.0-1.fc17\n\nDetails about builds:\n\n\n================================================================================\n libseccomp-2.1.0-1.fc20 (FEDORA-%s-a3bbe1a8f2)\n Enhanced seccomp library\n--------------------------------------------------------------------------------\nUpdate Information:\n\nUseful details!\n--------------------------------------------------------------------------------\nReferences:\n\n  [ 1 ] Bug #12345 - None\n        https://bugzilla.redhat.com/show_bug.cgi?id=12345\n  [ 2 ] CVE-1985-0110\n        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-1985-0110\n--------------------------------------------------------------------------------\n\n' % (config.get('fedora_test_announce_list'), time.strftime('%Y'))), repr(body)

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

        from bodhi.exceptions import RepodataException
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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
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
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override',
                branch=u'f18')
            db.add(release)
            build = Build(nvr=u'bodhi-2.0-1.fc18', release=release,
                          package=up.builds[0].package)
            db.add(build)
            update = Update(
                title=u'bodhi-2.0-1.fc18',
                builds=[build], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release)
            update.type = UpdateType.security
            db.add(update)

            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        self.msg['body']['msg']['updates'] += ['bodhi-2.0-1.fc18']

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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
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
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override',
                branch=u'f18')
            db.add(release)
            build = Build(nvr=u'bodhi-2.0-1.fc18', release=release,
                          package=up.builds[0].package)
            db.add(build)
            update = Update(
                title=u'bodhi-2.0-1.fc18',
                builds=[build], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release)
            update.type = UpdateType.enhancement
            db.add(update)

            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        self.msg['body']['msg']['updates'] += ['bodhi-2.0-1.fc18']

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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
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
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override',
                branch=u'f18')
            db.add(release)
            build = Build(nvr=u'bodhi-2.0-1.fc18', release=release,
                          package=up.builds[0].package)
            db.add(build)
            update = Update(
                title=u'bodhi-2.0-1.fc18',
                builds=[build], user=user,
                status=UpdateStatus.testing,
                request=UpdateRequest.stable,
                notes=u'Useful details!', release=release)
            update.type = UpdateType.security
            db.add(update)

            # Wipe out the tag cache so it picks up our new release
            Release._tag_cache = None

        self.msg['body']['msg']['updates'] += ['bodhi-2.0-1.fc18']

        self.masher.consume(self.msg)

        # Ensure that F18 and F17 run in parallel
        calls = publish.mock_calls
        if calls[1] == mock.call(
            msg={'repo': u'f18-updates',
                 'updates': [u'bodhi-2.0-1.fc18'],
                 'agent': 'lmacken'},
            force=True,
            topic='mashtask.mashing'):
            self.assertEquals(calls[2], mock.call(
                msg={'repo': u'f17-updates',
                     'updates': [u'bodhi-2.0-1.fc17'],
                     'agent': 'lmacken'},
                force=True,
                topic='mashtask.mashing'))
        elif calls[1] == self.assertEquals(calls[1], mock.call(
            msg={'repo': u'f17-updates',
                 'updates': [u'bodhi-2.0-1.fc17'],
                 'agent': 'lmacken'},
            force=True,
            topic='mashtask.mashing')):
            self.assertEquals(calls[2], mock.call(
                msg={'repo': u'f18-updates',
                     'updates': [u'bodhi-2.0-1.fc18']},
                force=True,
                topic='mashtask.mashing'))


    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.util.cmd')
    def test_update_comps(self, cmd, *args):
        cmd.return_value = '', '', 0
        self.masher.consume(self.msg)
        self.assertIn(mock.call(['git', 'pull'], mock.ANY), cmd.mock_calls)
        self.assertIn(mock.call(['make'], mock.ANY), cmd.mock_calls)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_mash(self, cmd, publish, *args):
        cmd.return_value = '', '', 0

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request('bodhi-2.0-1.fc17')

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
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_failed_gating(self, cmd, publish, *args):
        cmd.return_value = '', '', 0

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request('bodhi-2.0-1.fc17')

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
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_absent_gating(self, cmd, publish, *args):
        cmd.return_value = '', '', 0

        # Set the request to stable right out the gate so we can test gating
        self.set_stable_request('bodhi-2.0-1.fc17')

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

    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    @mock.patch('bodhi.bugs.bugtracker.modified')
    @mock.patch('bodhi.bugs.bugtracker.on_qa')
    def test_modify_testing_bugs(self, on_qa, modified, *args):
        self.masher.consume(self.msg)
        on_qa.assert_called_once_with(12345,
                u'bodhi-2.0-1.fc17 has been pushed to the Fedora 17 testing repository. If problems still persist, please make note of it in this bug report.\nSee https://fedoraproject.org/wiki/QA:Updates_Testing for\ninstructions on how to install test updates.\nYou can provide feedback for this update here: http://0.0.0.0:6543/updates/FEDORA-2016-a3bbe1a8f2')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    @mock.patch('bodhi.bugs.bugtracker.comment')
    @mock.patch('bodhi.bugs.bugtracker.close')
    def test_modify_stable_bugs(self, close, comment, *args):
        self.set_stable_request('bodhi-2.0-1.fc17')
        t = MasherThread(u'F17', u'stable', [u'bodhi-2.0-1.fc17'],
                         'ralph', log, self.db_factory, self.tempdir)
        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None
        close.assert_called_with(
            12345,
            versions=dict(bodhi=u'bodhi-2.0-1.fc17'),
            comment=u'bodhi-2.0-1.fc17 has been pushed to the Fedora 17 stable repository. If problems still persist, please make note of it in this bug report.')

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_status_comment_testing(self,  *args):
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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_status_comment_stable(self,  *args):
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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_get_security_updates(self,  *args):
        build = u'bodhi-2.0-1.fc17'
        t = MasherThread(u'F17', u'testing', [build],
                         'ralph', log, self.db_factory, self.tempdir)
        with self.db_factory() as session:
            t.db = session
            u = session.query(Update).one()
            u.type = UpdateType.security
            u.status = UpdateStatus.testing
            u.request = None
            release = session.query(Release).one()
            updates = t.get_security_updates(release.long_name)
            self.assertEquals(len(updates), 1)
            self.assertEquals(updates[0].title, build)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_unlock_updates(self,  *args):
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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_resume_push(self,  *args):
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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_stable_requirements_met_during_push(self,  *args):
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
            self.assertEquals(up.request, UpdateRequest.stable)

    @mock.patch(**mock_taskotron_results)
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
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
    @mock.patch('bodhi.consumers.masher.MasherThread.update_comps')
    @mock.patch('bodhi.consumers.masher.MashThread.run')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.consumers.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.consumers.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.consumers.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_obsolete_older_updates(self, publish, *args):
        otherbuild = 'bodhi-2.0-2.fc17'
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
            build = Build(nvr=otherbuild, package=oldupdate.builds[0].package)
            session.add(build)
            update = Update(title=otherbuild, builds=[build], type=UpdateType.bugfix,
                    request=UpdateRequest.testing, notes=u'second update',
                    user=oldupdate.user, release=oldupdate.release)
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
