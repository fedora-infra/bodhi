import unittest
import json
import tw2.core as twc

from kitchen.iterutils import iterate
from nose.tools import eq_
from webtest import TestApp
from sqlalchemy import create_engine

from bodhi import main
from bodhi.models import (
    Base, DBSession, Release, Update, User, Package, Build, Bug, UpdateType, Group,
)

app_settings = {
    'sqlalchemy.url': 'sqlite://',
    'mako.directories': 'bodhi:templates',
    'session.type': 'memory',
    'session.key': 'testing',
    'cache.type': 'memory',
    'cache.regions': 'default_term, second, short_term, long_term',
    'cache.second.expire': '1',
    'cache.short_term.expire': '60',
    'cache.default_term.expire': '300',
    'cache.long_term.expire': '3600',
    'acl_system': 'dummy',
    'buildsystem': 'dummy',
    'important_groups': 'proventesters provenpackager releng',
    'admin_packager_groups': 'provenpackager',
}


def populate():
    session = DBSession()
    user = User(name=u'guest')
    session.add(user)
    group = Group(name=u'provenpackager')
    session.add(group)
    release = Release(
        name=u'F17', long_name=u'Fedora 17',
        id_prefix=u'FEDORA', dist_tag=u'f17')
    session.add(release)
    pkg = Package(name=u'bodhi')
    session.add(pkg)
    build = Build(nvr=u'bodhi-2.0-1', release=release, package=pkg)
    session.add(build)
    update = Update(
        builds=[build], user=user,
        notes=u'Useful details!', release=release)
    update.type = UpdateType.bugfix
    bug = Bug(bug_id=12345)
    session.add(bug)
    update.bugs.append(bug)
    session.add(update)
    session.flush()


app = None

def setup():
    global app
    app = TestApp(main({}, testing=u'guest', **app_settings))


class TestWSGIApp(unittest.TestCase):

    def setUp(self):
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        populate()

    def tearDown(self):
        DBSession.remove()

    def get_update(self, builds=u'bodhi-2.0-1', stablekarma=3, unstablekarma=-3):
        if isinstance(builds, list):
            builds = u','.join(builds)
        return {
            'builds': builds,
            'bugs': u'',
            'notes': u'this is a test update',
            'type': u'bugfix',
            'stablekarma': stablekarma,
            'unstablekarma': unstablekarma,
        }

    def test_home(self):
        res = app.get('/', status=200)
        assert 'Logout' in res, res

    def test_invalid_build_name(self):
        res = app.post('/save', self.get_update(u'bodhi-2.0-1,invalidbuild-1.0'))
        assert 'Invalid build' in res, res

    def test_empty_build_name(self):
        res = app.post('/save', self.get_update([u'']))
        assert '{"builds.0": "Required"}' in res, res

    def test_valid_tag(self):
        res = app.post('/save', self.get_update())
        assert 'Invalid tag' not in res, res

    def test_invalid_tag(self):
        session = DBSession()
        map(session.delete, session.query(Update).all())
        map(session.delete, session.query(Build).all())
        num = session.query(Update).count()
        assert num == 0, num
        res = app.post('/save', self.get_update(u'bodhi-1.0-1'))
        assert 'Invalid tag' in res, res

    def test_old_build(self):
        res = app.post('/save', self.get_update(u'bodhi-1.9-1'))
        assert 'Invalid build: bodhi-1.9-1 is older than bodhi-2.0-1' in res, res

    def test_duplicate_build(self):
        res = app.post('/save', self.get_update([u'bodhi-2.0-2', u'bodhi-2.0-2']))
        assert 'Duplicate builds' in res, res

    def test_multiple_builds_of_same_package(self):
        res = app.post('/save', self.get_update([u'bodhi-2.0-2', u'bodhi-2.0-3']))
        assert 'Multiple bodhi builds specified' in res, res

    def test_invalid_autokarma(self):
        res = app.post('/save', self.get_update(stablekarma=-1))
        assert '-1 is less than minimum value 1' in res, res
        res = app.post('/save', self.get_update(unstablekarma=1))
        assert '1 is greater than maximum value -1' in res, res

    def test_duplicate_update(self):
        res = app.post('/save', self.get_update(u'bodhi-2.0-1'))
        assert 'Update for bodhi-2.0-1 already exists' in res, res

    def test_no_privs(self):
        session = DBSession()
        user = User(name=u'bodhi')
        session.add(user)
        session.flush()
        app = TestApp(main({}, testing=u'bodhi', **app_settings))
        res = app.post('/save', self.get_update(u'bodhi-2.1-1'))
        assert 'bodhi does not have commit access to bodhi' in res, res

    def test_provenpackager_privs(self):
        "Ensure provenpackagers can push updates for any package"
        session = DBSession()
        user = User(name=u'bodhi')
        session.add(user)
        session.flush()
        group = session.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)

        app = main({}, testing=u'bodhi', **app_settings)
        app = TestApp(twc.make_middleware(app))
        res = app.post('/save', self.get_update(u'bodhi-2.1-1'))
        assert 'bodhi does not have commit access to bodhi' not in res, res
        # TODO; uncomment once we're actually creating updates properly
        #build = session.query(Build).filter_by(nvr=u'bodhi-2.1-1').one()
        #assert len(build.updates) == 1

    def test_pkgdb_outage(self):
        "Test the case where our call to the pkgdb throws an exception"
        settings = app_settings.copy()
        settings['acl_system'] = 'pkgdb'
        settings['pkgdb_url'] = 'invalidurl'
        app = TestApp(main({}, testing=u'guest', **settings))
        res = app.post('/save', self.get_update(u'bodhi-2.0-2'))
        assert "Unable to access the Package Database. Please try again later." in res, res

    def test_invalid_acl_system(self):
        settings = app_settings.copy()
        settings['acl_system'] = 'null'
        app = TestApp(main({}, testing=u'guest', **settings))
        res = app.post('/save', self.get_update(u'bodhi-2.0-2'))
        assert "guest does not have commit access to bodhi" in res, res
