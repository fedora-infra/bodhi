import unittest

from datetime import datetime, timedelta
from webtest import TestApp
from sqlalchemy import create_engine
from sqlalchemy import event

from bodhi import main
from bodhi.models import (
    Base,
    Bug,
    Build,
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


class BaseWSGICase(unittest.TestCase):
    app_settings = {
        'sqlalchemy.url': 'sqlite://',
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
    }

    def setUp(self):
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        self.populate()
        self.app = TestApp(main({}, testing=u'guest', **self.app_settings))

        # Track sql statements in every test
        self.sql_statements = []
        def track(conn, cursor, statement, param, ctx, many):
            self.sql_statements.append(statement)

        event.listen(engine, "before_cursor_execute", track)

    def tearDown(self):
        DBSession.remove()

    def populate(self):
        session = DBSession()
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
            id_prefix=u'FEDORA', dist_tag=u'f17', version='17')
        session.add(release)
        pkg = Package(name=u'bodhi')
        session.add(pkg)
        user.packages.append(pkg)
        build = Build(nvr=u'bodhi-2.0-1.fc17', release=release, package=pkg)
        session.add(build)
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
