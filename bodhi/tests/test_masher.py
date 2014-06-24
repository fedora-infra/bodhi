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
import unittest
import tempfile
import transaction

from datetime import datetime
from contextlib import contextmanager
from sqlalchemy import create_engine

from bodhi import buildsys, log
from bodhi.config import config
from bodhi.masher import Masher, MasherThread
from bodhi.models import (DBSession, Base, Update, User, Group, Release,
                          Package, Build, TestCase, UpdateRequest, UpdateType,
                          Bug, CVE, Comment, ReleaseState, BuildrootOverride)


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
        db_path = 'sqlite:///%s' self.db_filename
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
            self.populate(session)

        with self.db_factory() as session:
            assert session.query(Update).count() == 1

        self.koji = buildsys.get_session()
        self.koji.clear()  # clear out our dev introspection

        self.msg = makemsg()
        self.masher = Masher(FakeHub(), db_factory=self.db_factory)

    def tearDown(self):
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

    @mock.patch('bodhi.notifications.publish')
    def test_update_locking(self, publish):
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

    @mock.patch('bodhi.notifications.publish')
    def test_tags(self, publish):
        # Make the build a buildroot override as well
        title = self.msg['body']['msg']['updates']
        with self.db_factory() as session:
            release = session.query(Update).one().release
            build = session.query(Build).one()
            self.koji.__tagged__[title] = [release.override_tag,
                                           release.pending_testing_tag]

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
        self.assertEquals(self.koji.__untag__[0], (release.pending_testing_tag, build.nvr))
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
        self.assertEquals(self.koji.__untag__[0], (release.override_tag, u'bodhi-2.0-1.fc17'))

        # Check that the override got expired
        with self.db_factory() as session:
            ovrd = session.query(BuildrootOverride).one()
            self.assertIsNotNone(ovrd.expired_date)

            # Check that the request_complete method got run
            up = session.query(Update).one()
            self.assertIsNone(up.request)

    def test_statefile(self):
        t = MasherThread(u'F17', u'testing', [u'bodhi-2.0-1.fc17'], log, self.db_factory)
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

    def populate(self, session):
        user = User(name=u'guest')
        session.add(user)
        provenpackager = Group(name=u'provenpackager')
        session.add(provenpackager)
        packager = Group(name=u'packager')
        session.add(packager)
        session.flush()
        user.groups.append(packager)
        release = Release(
            name=u'F17', long_name=u'Fedora 17',
            id_prefix=u'FEDORA', version='17',
            dist_tag=u'f17', stable_tag=u'f17-updates',
            testing_tag=u'f17-updates-testing',
            candidate_tag=u'f17-updates-candidate',
            pending_testing_tag=u'f17-updates-testing-pending',
            pending_stable_tag=u'f17-updates-pending',
            override_tag=u'f17-override')
        session.add(release)
        pkg = Package(name=u'bodhi')
        session.add(pkg)
        user.packages.append(pkg)
        build = Build(nvr=u'bodhi-2.0-1.fc17', release=release, package=pkg)
        session.add(build)
        override = BuildrootOverride(build=build, submitter=user,
                                     expiration_date=datetime.utcnow(),
                                     notes='foo')
        session.add(override)
        testcase = TestCase(name=u'Wat')
        session.add(testcase)
        pkg.test_cases.append(testcase)
        update = Update(
            title=u'bodhi-2.0-1.fc17',
            builds=[build], user=user,
            request=UpdateRequest.testing,
            notes=u'Useful details!', release=release,
            date_submitted=datetime(1984, 11, 02))
        update.type = UpdateType.bugfix
        bug = Bug(bug_id=12345)
        session.add(bug)
        update.bugs.append(bug)
        cve = CVE(cve_id="CVE-1985-0110")
        session.add(cve)
        update.cves.append(cve)
        comment = Comment(karma=1, text="wow. amaze.")
        session.add(comment)
        comment.user = user
        update.comments.append(comment)
        comment = Comment(karma=0, text="srsly.  pretty good.", anonymous=True)
        session.add(comment)
        update.comments.append(comment)
        session.add(update)
        session.flush()
