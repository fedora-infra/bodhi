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
import json
import shutil
import unittest
import tempfile
import transaction

from contextlib import contextmanager
from sqlalchemy import create_engine

from bodhi import buildsys, log
from bodhi.config import config
from bodhi.masher import Masher, MasherThread
from bodhi.models import (DBSession, Base, Update, User, Group, Release,
                          Package, Build, TestCase, UpdateRequest, UpdateType,
                          Bug, CVE, Comment, ReleaseState, BuildrootOverride,
                          UpdateStatus)
from bodhi.tests import populate

from bodhi.util import mkmetadatadir


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
        body = {'updates': 'bodhi-2.0-1.fc17'}
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


@contextmanager
def transactional_session_maker():
    """Provide a transactional scope around a series of operations."""
    session = DBSession()
    transaction.begin()
    try:
        yield session
        transaction.commit()
    except:
        transaction.abort()
        raise
    finally:
        session.close()


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
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        self.db_factory = transactional_session_maker

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
            DBSession.remove()
        finally:
            try:
                os.remove(self.db_filename)
            except:
                pass

    @mock.patch('bodhi.notifications.publish')
    def test_invalid_signature(self, publish):
        """Make sure the masher ignores messages that aren't signed with the
        appropriate releng cert
        """
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

    @mock.patch('bodhi.masher.MasherThread.update_comps')
    @mock.patch('bodhi.masher.MashThread.run')
    @mock.patch('bodhi.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_update_locking(self, publish, *args):
        with self.db_factory() as session:
            up = session.query(Update).one()
            self.assertFalse(up.locked)

        self.masher.consume(self.msg)

        # Ensure that fedmsg was called 4 times
        self.assertEquals(len(publish.call_args_list), 4)

        # Also, ensure we reported success
        publish.assert_called_with(
            topic="mashtask.complete",
            msg=dict(success=True))

        with self.db_factory() as session:
            # Ensure that the update was locked
            up = session.query(Update).one()
            self.assertTrue(up.locked)

    @mock.patch('bodhi.masher.MasherThread.update_comps')
    @mock.patch('bodhi.masher.MashThread.run')
    @mock.patch('bodhi.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_tags(self, publish, *args):
        # Make the build a buildroot override as well
        title = self.msg['body']['msg']['updates']
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
            msg=dict(success=True))

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

    def test_statefile(self):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'], log, self.db_factory, self.tempdir)
        t.id = 'f17-updates-testing'
        t.init_state()
        t.save_state()
        self.assertTrue(os.path.exists(t.mash_lock))
        with file(t.mash_lock) as f:
            state = json.load(f)
        try:
            self.assertEquals(state, {u'tagged': False, u'updates':
                [u'bodhi-2.0-1.fc17'], u'completed_repos': []})
        finally:
            t.remove_state()

    @mock.patch('bodhi.masher.MasherThread.update_comps')
    @mock.patch('bodhi.masher.MashThread.run')
    @mock.patch('bodhi.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_testing_digest(self, *args):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'],
                         log, self.db_factory, self.tempdir)
        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None
        self.assertEquals(t.testing_digest[u'Fedora 17'][u'bodhi-2.0-1.fc17'], """\
================================================================================
 libseccomp-2.1.0-1.fc20 (None)
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

""")

    def test_sanity_check(self):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'],
                         log, self.db_factory, self.tempdir)
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
            repo = os.path.join(t.path, arch)
            os.mkdir(repo)
            mkmetadatadir(repo)

        t.sanity_check_repo()

        # test with truncated/busted repodata
        xml = os.path.join(t.path, 'i386', 'repodata', 'repomd.xml')
        repomd = open(xml).read()
        with open(xml, 'w') as f:
            f.write(repomd[:-10])

        from yum.Errors import RepoMDError
        try:
            t.sanity_check_repo()
            assert False, 'Busted metadata passed'
        except RepoMDError:
            pass

    def test_stage(self):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'],
                         log, self.db_factory, self.tempdir)
        t.id = 'f17-updates-testing'
        t.init_path()
        t.stage_repo()
        stage_dir = config.get('mash_stage_dir')
        link = os.path.join(stage_dir, t.id)
        self.assertTrue(os.path.islink(link))

    @mock.patch('bodhi.masher.MasherThread.update_comps')
    @mock.patch('bodhi.masher.MashThread.run')
    @mock.patch('bodhi.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_security_update_priority(self, publish, *args):
        with self.db_factory() as db:
            up = db.query(Update).one()
            user = db.query(User).one()

            # Create a security update for a different release
            release = Release(
                name=u'F18', long_name=u'Fedora 18',
                id_prefix=u'FEDORA', version='18',
                dist_tag=u'f18', stable_tag=u'f18-updates',
                testing_tag=u'f18-updates-testing',
                candidate_tag=u'f18-updates-candidate',
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override')
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

        self.msg['body']['msg']['updates'] += ' bodhi-2.0-1.fc18'

        self.masher.consume(self.msg)

        # Ensure that F18 runs before F17
        calls = publish.mock_calls
        self.assertEquals(calls[1], mock.call(msg={'repo': u'f18-updates',
            'updates': [u'bodhi-2.0-1.fc18']}, topic='mashtask.mashing'))
        self.assertEquals(calls[3], mock.call(msg={'success': True},
            topic='mashtask.complete'))
        self.assertEquals(calls[4], mock.call(msg={'repo': u'f17-updates-testing',
            'updates': [u'bodhi-2.0-1.fc17']}, topic='mashtask.mashing'))
        self.assertEquals(calls[-1], mock.call(msg={'success': True},
            topic='mashtask.complete'))

    @mock.patch('bodhi.masher.MasherThread.update_comps')
    @mock.patch('bodhi.masher.MashThread.run')
    @mock.patch('bodhi.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_security_update_priority_testing(self, publish, *args):
        with self.db_factory() as db:
            up = db.query(Update).one()
            up.type = UpdateType.security
            up.request = UpdateRequest.testing
            user = db.query(User).one()

            # Create a security update for a different release
            release = Release(
                name=u'F18', long_name=u'Fedora 18',
                id_prefix=u'FEDORA', version='18',
                dist_tag=u'f18', stable_tag=u'f18-updates',
                testing_tag=u'f18-updates-testing',
                candidate_tag=u'f18-updates-candidate',
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override')
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

        self.msg['body']['msg']['updates'] += ' bodhi-2.0-1.fc18'

        self.masher.consume(self.msg)

        # Ensure that F17 updates-testing runs before F18
        calls = publish.mock_calls
        self.assertEquals(calls[1], mock.call(msg={'repo': u'f17-updates-testing',
            'updates': [u'bodhi-2.0-1.fc17']}, topic='mashtask.mashing'))
        self.assertEquals(calls[3], mock.call(msg={'success': True},
            topic='mashtask.complete'))
        self.assertEquals(calls[4], mock.call(msg={'repo': u'f18-updates',
            'updates': [u'bodhi-2.0-1.fc18']}, topic='mashtask.mashing'))
        self.assertEquals(calls[-1], mock.call(msg={'success': True},
            topic='mashtask.complete'))

    @mock.patch('bodhi.masher.MasherThread.update_comps')
    @mock.patch('bodhi.masher.MashThread.run')
    @mock.patch('bodhi.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    def test_security_updates_parallel(self, publish, *args):
        with self.db_factory() as db:
            up = db.query(Update).one()
            up.type = UpdateType.security
            up.status = UpdateStatus.testing
            up.request = UpdateRequest.stable
            user = db.query(User).one()

            # Create a security update for a different release
            release = Release(
                name=u'F18', long_name=u'Fedora 18',
                id_prefix=u'FEDORA', version='18',
                dist_tag=u'f18', stable_tag=u'f18-updates',
                testing_tag=u'f18-updates-testing',
                candidate_tag=u'f18-updates-candidate',
                pending_testing_tag=u'f18-updates-testing-pending',
                pending_stable_tag=u'f18-updates-pending',
                override_tag=u'f18-override')
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

        self.msg['body']['msg']['updates'] += ' bodhi-2.0-1.fc18'

        self.masher.consume(self.msg)

        # Ensure that F18 and F17 run in parallel
        calls = publish.mock_calls
        if calls[1] == mock.call(msg={'repo': u'f18-updates',
            'updates': [u'bodhi-2.0-1.fc18']}, topic='mashtask.mashing'):
            self.assertEquals(calls[2], mock.call(msg={'repo': u'f17-updates',
                'updates': [u'bodhi-2.0-1.fc17']}, topic='mashtask.mashing'))
        elif calls[1] == self.assertEquals(calls[1], mock.call(msg={'repo': u'f17-updates',
            'updates': [u'bodhi-2.0-1.fc17']}, topic='mashtask.mashing')):
            self.assertEquals(calls[2], mock.call(msg={'repo': u'f18-updates',
                'updates': [u'bodhi-2.0-1.fc18']}, topic='mashtask.mashing'))


    @mock.patch('bodhi.masher.MashThread.run')
    @mock.patch('bodhi.masher.MasherThread.wait_for_mash')
    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.util.cmd')
    def test_update_comps(self, cmd, *args):
        self.masher.consume(self.msg)
        self.assertIn(mock.call(['git', 'pull'], mock.ANY), cmd.mock_calls)
        self.assertIn(mock.call(['make'], mock.ANY), cmd.mock_calls)

    @mock.patch('bodhi.masher.MasherThread.sanity_check_repo')
    @mock.patch('bodhi.masher.MasherThread.stage_repo')
    @mock.patch('bodhi.masher.MasherThread.generate_updateinfo')
    @mock.patch('bodhi.masher.MasherThread.wait_for_sync')
    @mock.patch('bodhi.notifications.publish')
    @mock.patch('bodhi.util.cmd')
    def test_mash(self, cmd, publish, *args):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'], log,
                         self.db_factory, self.tempdir)

        with self.db_factory() as session:
            t.db = session
            t.work()
            t.db = None

        # Also, ensure we reported success
        publish.assert_called_with(topic="mashtask.complete",
                                   msg=dict(success=True))
        publish.assert_any_call(topic='update.complete.testing',
                                msg=mock.ANY)

        self.assertIn(mock.call(['mash'] + [mock.ANY] * 7), cmd.mock_calls)
        self.assertEquals(len(t.state['completed_repos']), 1)
