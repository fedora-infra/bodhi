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
import unittest

from datetime import datetime, timedelta
from webtest import TestApp
from sqlalchemy import create_engine
from sqlalchemy import event

from bodhi import main, log
from bodhi.models import (
    Base,
    Bug,
    Build,
    BuildrootOverride,
    Comment,
    CVE,
    DBSession,
    Group,
    Package,
    Release,
    Update,
    UpdateType,
    User,
    UpdateStatus,
    UpdateRequest,
    TestCase,
)

FAITOUT = 'http://209.132.184.152/faitout/'
DB_PATH = 'sqlite://'
DB_NAME = None
if os.environ.get('BUILD_ID'):
    try:
        import requests
        req = requests.get('%s/new' % FAITOUT)
        if req.status_code == 200:
            DB_PATH = req.text
            DB_NAME = DB_PATH.rsplit('/', 1)[1]
            print 'Using faitout at: %s' % DB_PATH
    except:
        pass


class BaseWSGICase(unittest.TestCase):
    app_settings = {
        'sqlalchemy.url': DB_PATH,
        'mako.directories': 'bodhi:templates',
        'session.type': 'memory',
        'session.key': 'testing',
        'session.secret': 'foo',
        'dogpile.cache.backend': 'dogpile.cache.memory',
        'dogpile.cache.expiration_time': 0,
        'cache.type': 'memory',
        'cache.regions': 'default_term, second, short_term, long_term',
        'cache.second.expire': '1',
        'cache.short_term.expire': '60',
        'cache.default_term.expire': '300',
        'cache.long_term.expire': '3600',
        'acl_system': 'dummy',
        'buildsystem': 'dummy',
        'important_groups': 'proventesters provenpackager releng',
        'admin_groups': 'bodhiadmin releng',
        'admin_packager_groups': 'provenpackager',
        'mandatory_packager_groups': 'packager',
        'critpath_pkgs': 'kernel',
        'bugtracker': 'dummy',
        'stats_blacklist': 'bodhi autoqa',
        'system_users': 'bodhi autoqa',
        'max_update_length_for_ui': '70',
        'openid.provider': 'https://id.stg.fedoraproject.org',
        'test_case_base_url': 'https://fedoraproject.org/wiki/',
        'openid_template': '{username}.id.fedoraproject.org',
    }

    def setUp(self):
        engine = create_engine(DB_PATH)
        DBSession.configure(bind=engine)
        log.debug('Creating all models for %s' % engine)
        Base.metadata.create_all(engine)
        self.db = DBSession()
        self.populate()
        self.app = TestApp(main({}, testing=u'guest', **self.app_settings))

        # Track sql statements in every test
        self.sql_statements = []
        def track(conn, cursor, statement, param, ctx, many):
            self.sql_statements.append(statement)

        event.listen(engine, "before_cursor_execute", track)

    def tearDown(self):
        log.debug('Removing session')
        #self.db.remove()
        DBSession.remove()
        if DB_NAME:
            try:
                import requests
                req = requests.get('%s/clean/%s' % (FAITOUT, DB_NAME))
            except:
                pass

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

        expiration_date = datetime.now()
        expiration_date = expiration_date + timedelta(days=1)

        override = BuildrootOverride(build=build, submitter=user,
                                     notes=u'blah blah blah',
                                     expiration_date=expiration_date)
        self.db.add(override)

        self.db.flush()

    def get_update(self, builds=u'bodhi-2.0-1.fc17', stable_karma=3, unstable_karma=-3):
        if isinstance(builds, list):
            builds = u','.join(builds)
        return {
            'builds': builds,
            'bugs': u'',
            'notes': u'this is a test update',
            'type': u'bugfix',
            'stable_karma': stable_karma,
            'unstable_karma': unstable_karma,
        }
