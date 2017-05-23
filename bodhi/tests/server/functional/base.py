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

from webtest import TestApp

from bodhi.server import main
from bodhi.tests.server.base import BaseTestCase, DB_NAME, DB_PATH, FAITOUT


class BaseWSGICase(BaseTestCase):
    app_settings = {
        'authtkt.secret': 'sssshhhhhh',
        'sqlalchemy.url': DB_PATH,
        'mako.directories': 'bodhi:server/templates',
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
        'critpath.num_admin_approvals': 0,
        'bugtracker': 'dummy',
        'stats_blacklist': 'bodhi autoqa',
        'system_users': 'bodhi autoqa',
        'max_update_length_for_ui': '70',
        'openid.provider': 'https://id.stg.fedoraproject.org/openid/',
        'openid.url': 'https://id.stg.fedoraproject.org',
        'test_case_base_url': 'https://fedoraproject.org/wiki/',
        'openid_template': '{username}.id.fedoraproject.org',
        'site_requirements': u'rpmlint',
        'resultsdb_api_url': 'whatever',
        'base_address': 'http://0.0.0.0:6543',
        'cors_connect_src': 'http://0.0.0.0:6543',
        'cors_origins_ro': 'http://0.0.0.0:6543',
        'cors_origins_rw': 'http://0.0.0.0:6543',
    }

    def setUp(self):
        super(BaseWSGICase, self).setUp()
        self.app = TestApp(main({}, testing=u'guest', session=self.db, **self.app_settings))

    def tearDown(self):
        super(BaseWSGICase, self).tearDown()
        if DB_NAME:
            try:
                import requests
                requests.get('%s/clean/%s' % (FAITOUT, DB_NAME))
            except:
                pass

    def get_csrf_token(self):
        return self.app.get('/csrf').json_body['csrf_token']

    def get_update(self, builds='bodhi-2.0-1.fc17', stable_karma=3, unstable_karma=-3):
        if isinstance(builds, list):
            builds = ','.join(builds)
        if not isinstance(builds, str):
            builds = builds.encode('utf-8')
        return {
            'builds': builds,
            'bugs': u'',
            'notes': u'this is a test update',
            'type': u'bugfix',
            'autokarma': True,
            'stable_karma': stable_karma,
            'unstable_karma': unstable_karma,
            'requirements': u'rpmlint',
            'require_bugs': False,
            'require_testcases': True,
            'csrf_token': self.get_csrf_token(),
        }
