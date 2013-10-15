import unittest

from datetime import datetime, timedelta
from webtest import TestApp
from sqlalchemy import create_engine

from bodhi import main
from bodhi.models import (
    Base,
    Bug,
    Build,
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
    'mandatory_packager_groups': 'packager',
}


def populate():
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
    build = Build(nvr=u'bodhi-2.0-1', release=release, package=pkg)
    session.add(build)
    update = Update(
        title=u'bodhi-2.0-1',
        builds=[build], user=user,
        notes=u'Useful details!', release=release,
        date_submitted=datetime(1984, 11, 02))
    update.type = UpdateType.bugfix
    bug = Bug(bug_id=12345)
    session.add(bug)
    update.bugs.append(bug)
    cve = CVE(cve_id="CVE-1985-0110")
    session.add(cve)
    update.cves.append(cve)
    session.add(update)
    session.flush()


class TestWSGIApp(unittest.TestCase):

    def setUp(self):
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        populate()
        self.app = TestApp(main({}, testing=u'guest', **app_settings))

    def tearDown(self):
        DBSession.remove()

    def get_update(self, builds=u'bodhi-2.0-1', stable_karma=3, unstable_karma=-3):
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

    def test_home(self):
        res = self.app.get('/', status=200)
        assert 'Logout' in res, res

    def test_invalid_build_name(self):
        res = self.app.post_json('/updates', self.get_update(u'bodhi-2.0-1,invalidbuild-1.0'),
                                 status=400)
        assert 'Build not in name-version-release format' in res, res

    def test_empty_build_name(self):
        res = self.app.post_json('/updates', self.get_update([u'']), status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'builds.0')
        self.assertEquals(res.json_body['errors'][0]['description'], 'Required')

    def test_invalid_tag(self):
        session = DBSession()
        map(session.delete, session.query(Update).all())
        map(session.delete, session.query(Build).all())
        num = session.query(Update).count()
        assert num == 0, num
        res = self.app.post_json('/updates', self.get_update(u'bodhi-1.0-1'),
                                 status=400)
        assert 'Invalid tag' in res, res

    def test_old_build(self):
        res = self.app.post_json('/updates', self.get_update(u'bodhi-1.9-1'),
                                 status=400)
        assert 'Invalid build: bodhi-1.9-1 is older than bodhi-2.0-1' in res, res

    def test_duplicate_build(self):
        res = self.app.post_json('/updates',
            self.get_update([u'bodhi-2.0-2', u'bodhi-2.0-2']),
            status=400)
        assert 'Duplicate builds' in res, res

    def test_multiple_builds_of_same_package(self):
        res = self.app.post_json('/updates', self.get_update([u'bodhi-2.0-2',
                                                              u'bodhi-2.0-3']),
                                 status=400)
        assert 'Multiple bodhi builds specified' in res, res

    def test_invalid_autokarma(self):
        res = self.app.post_json('/updates', self.get_update(stable_karma=-1),
                                 status=400)
        assert '-1 is less than minimum value 1' in res, res
        res = self.app.post_json('/updates', self.get_update(unstable_karma=1),
                                 status=400)
        assert '1 is greater than maximum value -1' in res, res

    def test_duplicate_update(self):
        res = self.app.post_json('/updates', self.get_update(u'bodhi-2.0-1'),
                                 status=400)
        assert 'Update for bodhi-2.0-1 already exists' in res, res

    def test_no_privs(self):
        session = DBSession()
        user = User(name=u'bodhi')
        session.add(user)
        session.flush()
        app = TestApp(main({}, testing=u'bodhi', **app_settings))
        res = app.post_json('/updates', self.get_update(u'bodhi-2.1-1'),
                            status=400)
        assert 'bodhi does not have commit access to bodhi' in res, res

    def test_provenpackager_privs(self):
        "Ensure provenpackagers can push updates for any package"
        session = DBSession()
        user = User(name=u'bodhi')
        session.add(user)
        session.flush()
        group = session.query(Group).filter_by(name=u'provenpackager').one()
        user.groups.append(group)

        app = TestApp(main({}, testing=u'bodhi', **app_settings))
        res = app.post_json('/updates', self.get_update(u'bodhi-2.1-1'))
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
        res = app.post_json('/updates', self.get_update(u'bodhi-2.0-2'),
                            status=400)
        assert "Unable to access the Package Database. Please try again later." in res, res

    def test_invalid_acl_system(self):
        settings = app_settings.copy()
        settings['acl_system'] = 'null'
        app = TestApp(main({}, testing=u'guest', **settings))
        res = app.post_json('/updates', self.get_update(u'bodhi-2.0-2'),
                            status=400)
        assert "guest does not have commit access to bodhi" in res, res

    def test_404(self):
        self.app.get('/a', status=404)

    def test_list_updates(self):
        res = self.app.get('/updates')
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_approved_since(self):
        now = datetime.now()

        # Try with no approved updates first
        res = self.app.get('/updates',
                           {"approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        session = DBSession()
        session.query(Update).first().date_approved = now
        session.flush()

        # And try again
        res = self.app.get('/updates',
                           {"approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_approved_since(self):
        res = self.app.get('/updates', {"approved_since": "forever"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'approved_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_bugs(self):
        res = self.app.get('/updates', {"bugs": '12345'})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_bug(self):
        res = self.app.get('/updates', {"bugs": "cockroaches"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'bugs.0')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"cockroaches" is not a number')

    def test_list_updates_by_unexisting_bug(self):
        res = self.app.get('/updates', {"bugs": "19850110"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_critpath(self):
        res = self.app.get('/updates', {"critpath": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_invalid_critpath(self):
        res = self.app.get('/updates', {"critpath": "lalala"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'critpath')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"lalala" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_cves(self):
        res = self.app.get("/updates", {"cves": "CVE-1985-0110"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['cves'][0]['cve_id'], "CVE-1985-0110")

    def test_list_updates_by_unexisting_cve(self):
        res = self.app.get('/updates', {"cves": "CVE-2013-1015"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_invalid_cve(self):
        res = self.app.get('/updates', {"cves": "WTF-ZOMG-BBQ"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'cves.0')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"WTF-ZOMG-BBQ" is not a valid CVE id')

    def test_list_updates_by_date_submitted_invalid_date(self):
        """test filtering by submitted date with an invalid date"""
        res = self.app.get('/updates', {"submitted_since": "11-01-1984"},
            status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(body['errors'][0]['name'], 'submitted_since')
        self.assertEquals(body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_date_submitted_future_date(self):
        """test filtering by submitted date with future date"""
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d")

        res = self.app.get('/updates', {"submitted_since": tomorrow})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_date_submitted_valid(self):
        """test filtering by submitted date with valid data"""
        res = self.app.get('/updates', {"submitted_since": "1984-11-01"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_locked(self):
        res = self.app.get('/updates', {"locked": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_invalid_locked(self):
        res = self.app.get('/updates', {"locked": "maybe"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'locked')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"maybe" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_modified_since(self):
        now = datetime.now()

        # Try with no modified updates first
        res = self.app.get('/updates',
                           {"modified_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        session = DBSession()
        session.query(Update).first().date_modified = now
        session.flush()

        # And try again
        res = self.app.get('/updates',
                           {"modified_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_modified_since(self):
        res = self.app.get('/updates', {"modified_since": "the dawn of time"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'modified_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_package(self):
        res = self.app.get('/updates', {"packages": "bodhi"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_package(self):
        res = self.app.get('/updates', {"packages": "flash-player"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

    def test_list_updates_by_pushed(self):
        res = self.app.get('/updates', {"pushed": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['pushed'], False)

    def test_list_updates_by_invalid_pushed(self):
        res = self.app.get('/updates', {"pushed": "who knows?"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'pushed')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"who knows?" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_pushed_since(self):
        now = datetime.now()

        # Try with no pushed updates first
        res = self.app.get('/updates',
                           {"pushed_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        session = DBSession()
        session.query(Update).first().date_pushed = now
        session.flush()

        # And try again
        res = self.app.get('/updates',
                           {"pushed_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_pushed_since(self):
        res = self.app.get('/updates', {"pushed_since": "a while ago"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'pushed_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_qa_approved(self):
        res = self.app.get('/updates', {"qa_approved": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['pushed'], False)

    def test_list_updates_by_invalid_qa_approved(self):
        res = self.app.get('/updates', {"qa_approved": "ship it!"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'qa_approved')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"ship it!" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_qa_approved_since(self):
        now = datetime.now()

        # Try with no qa_approved updates first
        res = self.app.get('/updates',
                           {"qa_approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        session = DBSession()
        session.query(Update).first().qa_approval_date = now
        session.flush()

        # And try again
        res = self.app.get('/updates',
                           {"qa_approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_qa_approved_since(self):
        res = self.app.get('/updates', {"qa_approved_since": "just ship it already!"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'qa_approved_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_release_name(self):
        res = self.app.get('/updates', {"releases": "F17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_release_version(self):
        res = self.app.get('/updates', {"releases": "17"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_release(self):
        res = self.app.get('/updates', {"releases": "WinXP"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'releases')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid releases specified: WinXP')

    def test_list_updates_by_releng_approved(self):
        res = self.app.get('/updates', {"releng_approved": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approved'], False)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['pushed'], False)

    def test_list_updates_by_invalid_releng_approved(self):
        res = self.app.get('/updates', {"releng_approved": "sure..."},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'releng_approved')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"sure..." is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_releng_approved_since(self):
        now = datetime.now()

        # Try with no releng_approved updates first
        res = self.app.get('/updates',
                           {"releng_approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 0)

        # Now approve one
        session = DBSession()
        session.query(Update).first().releng_approval_date = now
        session.flush()

        # And try again
        res = self.app.get('/updates',
                           {"releng_approved_since": now.strftime("%Y-%m-%d")})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], now.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(len(up['bugs']), 1)
        self.assertEquals(up['bugs'][0]['bug_id'], 12345)

    def test_list_updates_by_invalid_releng_approved_since(self):
        res = self.app.get('/updates',
                           {"releng_approved_since": "just ship it already!"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'releng_approved_since')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          'Invalid date')

    def test_list_updates_by_request(self):
        res = self.app.get('/updates', {'request': "testing"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_request(self):
        res = self.app.get('/updates', {"request": "impossible"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'request')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"impossible" is not one of unpush, testing, obsolete, stable')

    def test_list_updates_by_security_approved(self):
        res = self.app.get('/updates', {"security_approved": "false"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['pushed'], False)

    def test_list_updates_by_invalid_security_approved(self):
        res = self.app.get('/updates', {"security_approved": "what's the CVE?"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'security_approved')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"what\'s the CVE?" is neither in (\'false\', \'0\') nor in (\'true\', \'1\')')

    def test_list_updates_by_severity(self):
        res = self.app.get('/updates', {"severity": "unspecified"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_severity(self):
        res = self.app.get('/updates', {"severity": "schoolmaster"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'severity')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"schoolmaster" is not one of high, urgent, medium, low, unspecified')

    def test_list_updates_by_status(self):
        res = self.app.get('/updates', {"status": "pending"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_status(self):
        res = self.app.get('/updates', {"status": "single"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'status')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"single" is not one of testing, processing, obsolete, stable, unpushed, pending')

    def test_list_updates_by_suggest(self):
        res = self.app.get('/updates', {"suggest": "unspecified"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_suggest(self):
        res = self.app.get('/updates', {"suggest": "no idea"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'suggest')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"no idea" is not one of logout, reboot, unspecified')

    def test_list_updates_by_type(self):
        res = self.app.get('/updates', {"type": "bugfix"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_type(self):
        res = self.app.get('/updates', {"type": "not_my"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'type')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          '"not_my" is not one of newpackage, bugfix, security, enhancement')

    def test_list_updates_by_username(self):
        res = self.app.get('/updates', {"user": "guest"})
        body = res.json_body
        self.assertEquals(len(body['updates']), 1)

        up = body['updates'][0]
        self.assertEquals(up['title'], u'bodhi-2.0-1')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'Useful details!')
        self.assertEquals(up['date_submitted'], u'1984-11-02 00:00:00')
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_list_updates_by_unexisting_username(self):
        res = self.app.get('/updates', {"user": "santa"},
                           status=400)
        body = res.json_body
        self.assertEquals(len(body.get('updates', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'user')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid user specified: santa")

    def test_put_json_update(self):
        self.app.put_json('/updates', self.get_update(), status=405)

    def test_post_json_update(self):
        self.app.post_json('/updates', self.get_update('bodhi-2.0.0-1'))

    def test_new_update(self):
        r = self.app.post_json('/updates', self.get_update('bodhi-2.0.0-2'))
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-2')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'this is a test update')
        self.assertIsNotNone(up['date_submitted'])
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)

    def test_edit_update(self):
        args = self.get_update('bodhi-2.0.0-2')
        r = self.app.post_json('/updates', args)
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3'
        r = self.app.post_json('/updates', args)
        up = r.json_body
        self.assertEquals(up['title'], u'bodhi-2.0.0-3')
        self.assertEquals(up['status'], u'pending')
        self.assertEquals(up['request'], u'testing')
        self.assertEquals(up['user']['name'], u'guest')
        self.assertEquals(up['release']['name'], u'F17')
        self.assertEquals(up['type'], u'bugfix')
        self.assertEquals(up['severity'], u'unspecified')
        self.assertEquals(up['suggest'], u'unspecified')
        self.assertEquals(up['close_bugs'], True)
        self.assertEquals(up['notes'], u'this is a test update')
        self.assertIsNotNone(up['date_submitted'])
        self.assertEquals(up['date_modified'], None)
        self.assertEquals(up['date_approved'], None)
        self.assertEquals(up['date_pushed'], None)
        self.assertEquals(up['qa_approved'], False)
        self.assertEquals(up['qa_approval_date'], None)
        self.assertEquals(up['security_approved'], False)
        self.assertEquals(up['security_approval_date'], None)
        self.assertEquals(up['releng_approval_date'], None)
        self.assertEquals(up['locked'], False)
        self.assertEquals(up['alias'], None)
        self.assertEquals(up['karma'], 0)
        self.assertEquals(up['comments'][0]['text'],
                          u'guest edited this update. New build(s): ' +
                          u'bodhi-2.0.0-3. Removed build(s): bodhi-2.0.0-2.')
        self.assertEquals(len(up['builds']), 1)
        self.assertEquals(up['builds'][0]['nvr'], u'bodhi-2.0.0-3')
        self.assertEquals(DBSession.query(Build).filter_by(nvr=u'bodhi-2.0.0-2').first(), None)

    def test_edit_stable_update(self):
        """Make sure we can't edit stable updates"""
        nvr = 'bodhi-2.0.0-2'
        args = self.get_update(nvr)
        r = self.app.post_json('/updates', args)
        up = DBSession.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.stable
        args['edited'] = args['builds']
        args['builds'] = 'bodhi-2.0.0-3'
        r = self.app.post_json('/updates', args, status=400)
        up = r.json_body
        self.assertEquals(up['status'], 'error')
        self.assertEquals(up['errors'][0]['description'], "Cannot edit stable updates")

    def test_push_untested_critpath_to_release(self):
        """
        Ensure that we cannot push an untested critpath update directly to
        stable.
        """
        args = self.get_update('bodhi-2.0.0-2')
        args['request'] = 'stable'
        up = self.app.post_json('/updates', args).json_body
        self.assertEquals(up['request'], 'testing')

    def test_obsoletion(self):
        nvr = 'bodhi-2.0.0-2'
        args = self.get_update(nvr)
        self.app.post_json('/updates', args)
        up = DBSession.query(Update).filter_by(title=nvr).one()
        up.status = UpdateStatus.testing
        up.request = None

        args = self.get_update('bodhi-2.0.0-3')
        r = self.app.post_json('/updates', args).json_body
        self.assertEquals(r['request'], 'testing')
        self.assertEquals(r['comments'][-1]['text'],
                          u'This update has obsoleted bodhi-2.0.0-2, '
                          'and has inherited its bugs and notes.')

        up = DBSession.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.obsolete)
        self.assertEquals(up.comments[-1].text,
                          u'This update has been obsoleted by bodhi-2.0.0-3')

    def test_obsoletion_with_open_request(self):
        nvr = 'bodhi-2.0.0-2'
        args = self.get_update(nvr)
        self.app.post_json('/updates', args)

        args = self.get_update('bodhi-2.0.0-3')
        r = self.app.post_json('/updates', args).json_body
        self.assertEquals(r['request'], 'testing')

        up = DBSession.query(Update).filter_by(title=nvr).one()
        self.assertEquals(up.status, UpdateStatus.pending)
        self.assertEquals(up.request, UpdateRequest.testing)
