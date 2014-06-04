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

from bodhi import buildsys
from bodhi.models import *
from bodhi.tests.functional.base import BaseWSGICase
from sqlalchemy import create_engine


class FakeHub(object):
    config = {
        'topic_prefix': 'org.fedoraproject',
        'environment': 'dev',
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


import unittest

class TestMasher(unittest.TestCase):

    def setUp(self):
        #super(TestMasher, self).setUp()
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        log.debug('Creating all models for %s' % engine)
        Base.metadata.create_all(engine)
        self.db = DBSession()
        import transaction
        with transaction.manager:
            self.populate()
        assert self.db.query(Update).count() == 1

    def tearDown(self):
        DBSession.remove()

    def test_masher(self):
        from bodhi.masher import Masher
        self.masher = Masher(FakeHub(), db=DBSession)
        up = self.db.query(Update).one()
        self.assertFalse(up.locked)
        self.masher.consume(makemsg())
        koji = buildsys.get_session()
        assert False, koji
        #self.assertTrue(up.locked)

    # test a basic push
    # ensure tags get moved

    #def test_masher_state(self):
    #    self.masher.save_state(self.db.query(Update).all())
    # test loading state
    # test resuming a push

    def populate(self):
        user = User(name=u'guest')
        self.db.add(user)
        provenpackager = Group(name=u'provenpackager')
        self.db.add(provenpackager)
        packager = Group(name=u'packager')
        self.db.add(packager)
        self.db.flush()
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
        self.db.add(release)
        pkg = Package(name=u'bodhi')
        self.db.add(pkg)
        user.packages.append(pkg)
        build = Build(nvr=u'bodhi-2.0-1.fc17', release=release, package=pkg)
        self.db.add(build)
        testcase = TestCase(name=u'Wat')
        self.db.add(testcase)
        pkg.test_cases.append(testcase)
        update = Update(
            title=u'bodhi-2.0-1.fc17',
            builds=[build], user=user,
            request=UpdateRequest.testing,
            notes=u'Useful details!', release=release,
            date_submitted=datetime(1984, 11, 02))
        update.type = UpdateType.bugfix
        bug = Bug(bug_id=12345)
        self.db.add(bug)
        update.bugs.append(bug)
        cve = CVE(cve_id="CVE-1985-0110")
        self.db.add(cve)
        update.cves.append(cve)
        comment = Comment(karma=1, text="wow. amaze.")
        self.db.add(comment)
        comment.user = user
        update.comments.append(comment)
        comment = Comment(karma=0, text="srsly.  pretty good.", anonymous=True)
        self.db.add(comment)
        update.comments.append(comment)
        self.db.add(update)
        self.db.flush()
