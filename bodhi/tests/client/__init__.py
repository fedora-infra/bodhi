# -*- coding: utf-8 -*-

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
"""This module contains test data for bodhi.client."""

from munch import Munch


EXAMPLE_COMMENT_MUNCH = Munch({
    u'comment': Munch({
        u'bug_feedback': [], u'user_id': 2897, u'author': u'bowlofeggs',
        u'timestamp': u'2017-02-28 18:08:13', u'testcase_feedback': [], u'karma_critpath': 0,
        u'update': Munch({
            u'date_testing': u'2017-02-13 22:56:06', u'old_updateid': None, u'pushed': True,
            u'require_testcases': False, u'date_stable': None, u'critpath': False,
            u'date_approved': None, u'stable_karma': 3, u'date_pushed': u'2017-02-13 22:56:06',
            u'requirements': u'', u'severity': u'low', u'autokarma': True,
            u'title': u'nodejs-grunt-wrap-0.3.0-2.fc25', u'suggest': u'unspecified',
            u'require_bugs': False, u'date_locked': None, u'type': u'newpackage',
            u'close_bugs': True, u'status': u'testing', u'meets_testing_requirements': True,
            u'date_submitted': u'2017-02-13 17:38:43', u'unstable_karma': -3,
            u'user': Munch({
                u'openid': u'bowlofeggs.id.fedoraproject.org', u'name': u'bowlofeggs',
                u'show_popups': True, u'id': 2897,
                u'avatar': u'AVATAR_URL',
                u'groups': [Munch({u'name': u'packager'})],
                u'email': u'email@example.com'}),
            u'locked': False,
            u'builds': [
                Munch({u'epoch': 0, u'nvr': u'nodejs-grunt-wrap-0.3.0-2.fc25', u'signed': True})],
            u'date_modified': None, u'url': u'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
            u'notes': u'New package.', u'request': None,
            u'bugs': [Munch({
                u'bug_id': 1420605, u'security': False, u'feedback': [], u'parent': False,
                u'title': (u'Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping '
                           u'project text files')})],
            u'alias': u'FEDORA-2017-c95b33872d', u'karma': 0,
            u'release': Munch({
                u'dist_tag': u'f25', u'name': u'F25', u'testing_tag': u'f25-updates-testing',
                u'pending_stable_tag': u'f25-updates-pending',
                u'pending_signing_tag': u'f25-signing-pending', u'long_name': u'Fedora 25',
                u'state': u'current', u'version': u'25', u'override_tag': u'f25-override',
                u'branch': u'f25', u'id_prefix': u'FEDORA',
                u'pending_testing_tag': u'f25-updates-testing-pending',
                u'stable_tag': u'f25-updates', u'candidate_tag': u'f25-updates-candidate'})}),
        u'update_id': 79733, u'karma': 0, u'anonymous': False, u'text': u'i found $10000',
        u'update_title': u'nodejs-grunt-wrap-0.3.0-2.fc25', u'id': 562626,
        u'user': Munch({
            u'openid': u'bowlofeggs.id.fedoraproject.org', u'name': u'bowlofeggs',
            u'show_popups': True, u'id': 2897, u'avatar': u'AVATAR_URL',
            u'groups': [Munch({u'name': u'packager'})], u'email': u'email@exampl.ecom'})}),
    u'caveats': []})

# EXAMPLE_COMMENT_MUNCH is expected to generate this output in update_str
EXPECTED_COMMENT_OUTPUT = """The following comment was added to nodejs-grunt-wrap-0.3.0-2.fc25
i found $10000
"""


EXAMPLE_COMPOSES_MUNCH = Munch({
    'composes': [
        Munch({
            u'release_id': 8, u'content_type': u'rpm',
            u'update_summary': [
                Munch({u'alias': u'FEDORA-EPEL-2018-50566f0a39', u'title': u'uwsgi-2.0.16-1.el7'}),
                Munch({u'alias': u'FEDORA-EPEL-2018-328e2b8c27', u'title': u'qtpass-1.2.1-3.el7'})],
            u'error_message': None, u'request': u'stable', u'state': u'requested',
            u'state_date': u'2018-03-15 17:25:22', u'checkpoints': u'{}',
            u'release': Munch({
                u'dist_tag': u'epel7', u'name': u'EPEL-7', u'testing_tag': u'epel7-testing',
                u'pending_stable_tag': u'epel7-pending',
                u'pending_signing_tag': u'epel7-signing-pending', u'long_name': u'Fedora EPEL 7',
                u'state': u'current', u'version': u'7', u'override_tag': u'epel7-override',
                u'branch': u'epel7', u'id_prefix': u'FEDORA-EPEL',
                u'pending_testing_tag': u'epel7-testing-pending', u'stable_tag': u'epel7',
                u'candidate_tag': u'epel7-testing-candidate'}),
            u'date_created': u'2018-03-15 17:25:22', u'security': True}),
        Munch({
            u'release_id': 8, u'content_type': u'rpm',
            u'update_summary': [
                Munch({u'alias': u'FEDORA-EPEL-2018-32f78e466c',
                       u'title': u'libmodulemd-1.1.0-1.el7'})],
            u'error_message': None, u'request': u'testing', u'state': u'requested',
            u'state_date': u'2018-03-15 17:25:22', u'checkpoints': u'{}',
            u'release': Munch({
                u'dist_tag': u'epel7', u'name': u'EPEL-7', u'testing_tag': u'epel7-testing',
                u'pending_stable_tag': u'epel7-pending',
                u'pending_signing_tag': u'epel7-signing-pending', u'long_name': u'Fedora EPEL 7',
                u'state': u'current', u'version': u'7', u'override_tag': u'epel7-override',
                u'branch': u'epel7', u'id_prefix': u'FEDORA-EPEL',
                u'pending_testing_tag': u'epel7-testing-pending', u'stable_tag': u'epel7',
                u'candidate_tag': u'epel7-testing-candidate'}),
            u'date_created': u'2018-03-15 17:25:22', u'security': False})]})


EXAMPLE_OVERRIDE_MUNCH = Munch({
    u'build_id': 108570, u'submission_date': u'2017-02-28 23:05:32', u'caveats': [],
    u'nvr': u'js-tag-it-2.0-1.fc25', u'expiration_date': u'2017-03-07 23:05:31',
    u'notes': u'No explanation given...', u'submitter_id': 2897,
    u'build': Munch(
        {u'epoch': 0, u'nvr': u'js-tag-it-2.0-1.fc25', u'signed': True, 'release_id': 15}),
    u'expired_date': None, u'submitter': Munch({
        u'openid': None, u'name': u'bowlofeggs', u'show_popups': True, u'id': 2897, u'avatar': None,
        u'groups': [Munch({u'name': u'packager'})], u'email': u'email@example.com'})})

EXAMPLE_OVERRIDE_MUNCH_CAVEATS = Munch({
    u'build_id': 108570, u'submission_date': u'2017-02-28 23:05:32',
    u'caveats': [Munch({u'description': u'this is a caveat'})],
    u'nvr': u'js-tag-it-2.0-1.fc25', u'expiration_date': u'2017-03-07 23:05:31',
    u'notes': u'No explanation given...', u'submitter_id': 2897,
    u'build': Munch({u'epoch': 0, u'nvr': u'js-tag-it-2.0-1.fc25', u'signed': True}),
    u'expired_date': None, u'submitter': Munch({
        u'openid': None, u'name': u'bowlofeggs', u'show_popups': True, u'id': 2897, u'avatar': None,
        u'groups': [Munch({u'name': u'packager'})], u'email': u'email@example.com'})})

EXAMPLE_EXPIRED_OVERRIDE_MUNCH = Munch({
    u'build_id': 108570, u'submission_date': u'2017-02-28 23:05:32', u'caveats': [],
    u'nvr': u'js-tag-it-2.0-1.fc25', u'expiration_date': u'2017-03-07 23:05:31',
    u'notes': u'This is an expired override', u'submitter_id': 2897,
    u'build': Munch({u'epoch': 0, u'nvr': u'js-tag-it-2.0-1.fc25', u'signed': True}),
    u'expired_date': '2017-03-07 23:05:31', u'submitter': Munch({
        u'openid': None, u'name': u'bowlofeggs', u'show_popups': True, u'id': 2897, u'avatar': None,
        u'groups': [Munch({u'name': u'packager'})], u'email': u'email@example.com'})})

EXAMPLE_QUERY_MUNCH = Munch({
    u'chrome': True,
    u'display_request': True,
    u'display_user': True,
    u'package': None,
    u'page': 1,
    u'pages': 1,
    u'rows_per_page': 20,
    u'total': 1,
    u'updates': [{
        u'alias': u'FEDORA-2017-c95b33872d',
        u'autokarma': True,
        u'content_type': u'rpm',
        u'bugs': [{
            u'bug_id': 1420605,
            u'feedback': [],
            u'parent': False,
            u'security': False,
            u'title': (u'Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping project '
                       u'text files')}],
        u'builds': [{
            u'epoch': 0,
            u'nvr': u'nodejs-grunt-wrap-0.3.0-2.fc25',
            u'signed': True}],
        u'close_bugs': True,
        u'comments': [
            {u'anonymous': False,
             u'bug_feedback': [],
             u'id': 561418,
             u'karma': 0,
             u'karma_critpath': 0,
             u'testcase_feedback': [],
             u'text': u'This update has been submitted for testing by bowlofeggs. ',
             u'timestamp': u'2017-02-13 17:38:43',
             u'update_id': 79733,
             u'user': {u'avatar': u'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                       u'email': None,
                       u'groups': [],
                       u'id': 91,
                       u'name': u'bodhi',
                       u'openid': u'bodhi.id.fedoraproject.org',
                       u'show_popups': True},
             u'user_id': 91},
            {u'anonymous': False,
             u'bug_feedback': [],
             u'id': 561619,
             u'karma': 0,
             u'karma_critpath': 0,
             u'testcase_feedback': [],
             u'text': u'This update has been pushed to testing.',
             u'timestamp': u'2017-02-14 00:55:18',
             u'update_id': 79733,
             u'user': {u'avatar': u'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                       u'email': None,
                       u'groups': [],
                       u'id': 91,
                       u'name': u'bodhi',
                       u'openid': u'bodhi.id.fedoraproject.org',
                       u'show_popups': True},
             u'user_id': 91},
            {u'anonymous': False,
             u'bug_feedback': [],
             u'id': 562620,
             u'karma': 0,
             u'karma_critpath': 0,
             u'testcase_feedback': [],
             u'text': u'i found $100',
             u'timestamp': u'2017-02-28 14:47:43',
             u'update_id': 79733,
             u'user': {u'avatar': u'AVATAR_URL',
                       u'email': u'email@example.com',
                       u'groups': [{u'name': u'packager'}],
                       u'id': 2897,
                       u'name': u'bowlofeggs',
                       u'openid': u'bowlofeggs.id.fedoraproject.org',
                       u'show_popups': True},
             u'user_id': 2897}],
        u'critpath': False,
        u'date_approved': None,
        u'date_locked': None,
        u'date_modified': None,
        u'date_pushed': u'2017-02-13 22:56:06',
        u'date_stable': None,
        u'date_submitted': u'2017-02-13 17:38:43',
        u'date_testing': u'2017-02-13 22:56:06',
        u'karma': 0,
        u'locked': False,
        u'meets_testing_requirements': True,
        u'notes': u'New package.',
        u'old_updateid': None,
        u'pushed': True,
        u'release': {u'branch': u'f25',
                     u'candidate_tag': u'f25-updates-candidate',
                     u'dist_tag': u'f25',
                     u'id_prefix': u'FEDORA',
                     u'long_name': u'Fedora 25',
                     u'name': u'F25',
                     u'override_tag': u'f25-override',
                     u'pending_signing_tag': u'f25-signing-pending',
                     u'pending_stable_tag': u'f25-updates-pending',
                     u'pending_testing_tag': u'f25-updates-testing-pending',
                     u'stable_tag': u'f25-updates',
                     u'state': u'current',
                     u'testing_tag': u'f25-updates-testing',
                     u'version': u'25'},
        u'request': None,
        u'require_bugs': False,
        u'require_testcases': False,
        u'requirements': u'',
        u'severity': u'low',
        u'stable_karma': 3,
        u'status': u'testing',
        u'submitter': u'bowlofeggs',
        u'suggest': u'unspecified',
        u'test_cases': [],
        u'title': u'nodejs-grunt-wrap-0.3.0-2.fc25',
        u'type': u'newpackage',
        u'unstable_karma': -3,
        u'updateid': u'FEDORA-2017-c95b33872d',
        u'url': u'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
        u'user': {u'avatar': u'AVATAR_URL',
                  u'email': u'email@example.com',
                  u'groups': [{u'name': u'packager'}],
                  u'id': 2897,
                  u'name': u'bowlofeggs',
                  u'openid': u'bowlofeggs.id.fedoraproject.org',
                  u'show_popups': True}}]})

EXPECTED_QUERY_OUTPUT = """\
================================================================================
     nodejs-grunt-wrap-0.3.0-2.fc25
================================================================================
   Update ID: FEDORA-2017-c95b33872d
Content Type: rpm
     Release: Fedora 25
      Status: testing
        Type: newpackage
    Severity: low
       Karma: 0
   Autokarma: True  [-3, 3]
        Bugs: 1420605 - Review Request: nodejs-grunt-wrap - A Grunt plugin for
            : wrapping project text files
       Notes: New package.
   Submitter: bowlofeggs
   Submitted: 2017-02-13 17:38:43
    Comments: bodhi - 2017-02-13 17:38:43 (karma 0)
              This update has been submitted for testing by bowlofeggs.
              bodhi - 2017-02-14 00:55:18 (karma 0)
              This update has been pushed to testing.
              bowlofeggs - 2017-02-28 14:47:43 (karma 0)
              i found $100

  http://localhost:6543/updates/FEDORA-2017-c95b33872d

1 updates found (1 shown)"""

EXAMPLE_QUERY_MUNCH_MULTI = Munch({
    u'chrome': True,
    u'display_request': True,
    u'display_user': True,
    u'package': None,
    u'page': 1,
    u'pages': 1,
    u'rows_per_page': 20,
    u'total': 2,
    u'updates': [{
        u'alias': u'FEDORA-2017-c95b33872d',
        u'autokarma': True,
        u'content_type': u'rpm',
        u'bugs': [{
            u'bug_id': 1420605,
            u'feedback': [],
            u'parent': False,
            u'security': False,
            u'title': (u'Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping project '
                       u'text files')}],
        u'builds': [{
            u'epoch': 0,
            u'nvr': u'nodejs-grunt-wrap-0.3.0-2.fc25',
            u'signed': True}],
        u'close_bugs': True,
        u'comments': [],
        u'critpath': False,
        u'date_approved': None,
        u'date_locked': None,
        u'date_modified': None,
        u'date_pushed': u'2017-02-13 22:56:06',
        u'date_stable': None,
        u'date_submitted': u'2017-02-13 17:38:43',
        u'date_testing': u'2017-02-13 22:56:06',
        u'karma': 0,
        u'locked': False,
        u'meets_testing_requirements': True,
        u'notes': u'New package.',
        u'old_updateid': None,
        u'pushed': True,
        u'release': {u'branch': u'f25',
                     u'candidate_tag': u'f25-updates-candidate',
                     u'dist_tag': u'f25',
                     u'id_prefix': u'FEDORA',
                     u'long_name': u'Fedora 25',
                     u'name': u'F25',
                     u'override_tag': u'f25-override',
                     u'pending_signing_tag': u'f25-signing-pending',
                     u'pending_stable_tag': u'f25-updates-pending',
                     u'pending_testing_tag': u'f25-updates-testing-pending',
                     u'stable_tag': u'f25-updates',
                     u'state': u'current',
                     u'testing_tag': u'f25-updates-testing',
                     u'version': u'25'},
        u'request': None,
        u'require_bugs': False,
        u'require_testcases': False,
        u'requirements': u'',
        u'severity': u'low',
        u'stable_karma': 3,
        u'status': u'testing',
        u'submitter': u'bowlofeggs',
        u'suggest': u'unspecified',
        u'test_cases': [],
        u'title': u'nodejs-grunt-wrap-0.3.0-2.fc25',
        u'type': u'newpackage',
        u'unstable_karma': -3,
        u'updateid': u'FEDORA-2017-c95b33872d',
        u'url': u'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
        u'user': {u'avatar': u'AVATAR_URL',
                  u'email': u'email@example.com',
                  u'groups': [{u'name': u'packager'}],
                  u'id': 2897,
                  u'name': u'bowlofeggs',
                  u'openid': u'bowlofeggs.id.fedoraproject.org',
                  u'show_popups': True}},
        {
        u'alias': u'FEDORA-2017-c95b33872d',
        u'autokarma': True,
        u'content_type': u'rpm',
        u'bugs': [{
            u'bug_id': 1420605,
            u'feedback': [],
            u'parent': False,
            u'security': False,
            u'title': (u'Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping project '
                       u'text files')}],
        u'builds': [{
            u'epoch': 0,
            u'nvr': u'nodejs-grunt-wrap-0.3.0-2.fc25',
            u'signed': True}],
        u'close_bugs': True,
        u'comments': [],
        u'critpath': False,
        u'date_approved': None,
        u'date_locked': None,
        u'date_modified': None,
        u'date_pushed': u'2017-02-13 22:56:06',
        u'date_stable': None,
        u'date_submitted': u'2017-02-13 17:38:43',
        u'date_testing': u'2017-02-13 22:56:06',
        u'karma': 0,
        u'locked': False,
        u'meets_testing_requirements': True,
        u'notes': u'New package.',
        u'old_updateid': None,
        u'pushed': True,
        u'release': {u'branch': u'f25',
                     u'candidate_tag': u'f25-updates-candidate',
                     u'dist_tag': u'f25',
                     u'id_prefix': u'FEDORA',
                     u'long_name': u'Fedora 25',
                     u'name': u'F25',
                     u'override_tag': u'f25-override',
                     u'pending_signing_tag': u'f25-signing-pending',
                     u'pending_stable_tag': u'f25-updates-pending',
                     u'pending_testing_tag': u'f25-updates-testing-pending',
                     u'stable_tag': u'f25-updates',
                     u'state': u'current',
                     u'testing_tag': u'f25-updates-testing',
                     u'version': u'25'},
        u'request': None,
        u'require_bugs': False,
        u'require_testcases': False,
        u'requirements': u'',
        u'severity': u'low',
        u'stable_karma': 3,
        u'status': u'testing',
        u'submitter': u'bowlofeggs',
        u'suggest': u'unspecified',
        u'test_cases': [],
        u'title': u'nodejs-grunt-wrap-0.3.0-2.fc25',
        u'type': u'newpackage',
        u'unstable_karma': -3,
        u'updateid': u'FEDORA-2017-c95b33872d',
        u'url': u'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
        u'user': {u'avatar': u'AVATAR_URL',
                  u'email': u'email@example.com',
                  u'groups': [{u'name': u'packager'}],
                  u'id': 2897,
                  u'name': u'bowlofeggs',
                  u'openid': u'bowlofeggs.id.fedoraproject.org',
                  u'show_popups': True}}]})

EXAMPLE_QUERY_OUTPUT_MULTI = """\
nodejs-grunt-wrap-0.3.0-2.fc25           rpm        testing   2017-02-13 (17)
nodejs-grunt-wrap-0.3.0-2.fc25           rpm        testing   2017-02-13 (17)
2 updates found (2 shown)
"""

EXAMPLE_QUERY_OVERRIDES_MUNCH = Munch({
    u'chrome': True,
    u'display_user': True,
    u'overrides': [
        {u'build': {
            u'epoch': 0,
            u'nvr': u'nodejs-grunt-wrap-0.3.0-2.fc25',
            u'signed': True},
         u'build_id': 108565,
         u'expiration_date': u'2017-03-07 14:30:36',
         u'expired_date': None,
         u'notes': u'No explanation given...',
         u'nvr': u'nodejs-grunt-wrap-0.3.0-2.fc25',
         u'submission_date': u'2017-02-28 14:30:37',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'python-pyramid-1.5.6-3.el7',
                    u'signed': True},
         u'build_id': 107673,
         u'expiration_date': u'2017-02-17 00:00:00',
         u'expired_date': None,
         u'notes': u'This is needed to build bodhi-2.4.0.',
         u'nvr': u'python-pyramid-1.5.6-3.el7',
         u'submission_date': u'2017-02-03 20:08:46',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'erlang-esip-1.0.8-1.fc25',
                    u'signed': True},
         u'build_id': 98946,
         u'expiration_date': u'2016-11-12 16:59:29',
         u'expired_date': u'2016-11-12 17:00:04',
         u'notes': u'needed for ejabberd',
         u'nvr': u'erlang-esip-1.0.8-1.fc25',
         u'submission_date': u'2016-11-10 16:59:35',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'erlang-stun-1.0.7-1.fc25',
                    u'signed': True},
         u'build_id': 98945,
         u'expiration_date': u'2016-11-12 00:00:00',
         u'expired_date': u'2016-11-12 00:00:22',
         u'notes': u'This is needed for ejabberd.',
         u'nvr': u'erlang-stun-1.0.7-1.fc25',
         u'submission_date': u'2016-11-10 16:21:53',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'erlang-iconv-1.0.2-1.fc25',
                    u'signed': True},
         u'build_id': 98942,
         u'expiration_date': u'2016-11-12 00:00:00',
         u'expired_date': u'2016-11-12 00:00:21',
         u'notes': u'This is needed for ejabberd.',
         u'nvr': u'erlang-iconv-1.0.2-1.fc25',
         u'submission_date': u'2016-11-10 15:45:17',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'erlang-stringprep-1.0.6-1.fc25',
                    u'signed': True},
         u'build_id': 98941,
         u'expiration_date': u'2016-11-12 00:00:00',
         u'expired_date': u'2016-11-12 00:00:24',
         u'notes': u'This is needed for ejabberd.',
         u'nvr': u'erlang-stringprep-1.0.6-1.fc25',
         u'submission_date': u'2016-11-10 15:43:52',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'erlang-fast_tls-1.0.7-1.fc25',
                    u'signed': True},
         u'build_id': 98940,
         u'expiration_date': u'2016-11-12 00:00:00',
         u'expired_date': u'2016-11-12 00:00:26',
         u'notes': u'This is needed for ejabberd.',
         u'nvr': u'erlang-fast_tls-1.0.7-1.fc25',
         u'submission_date': u'2016-11-10 15:41:09',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'erlang-fast_yaml-1.0.6-1.fc25',
                    u'signed': True},
         u'build_id': 98939,
         u'expiration_date': u'2016-11-12 00:00:00',
         u'expired_date': u'2016-11-12 00:00:27',
         u'notes': u'This is needed for ejabberd.',
         u'nvr': u'erlang-fast_yaml-1.0.6-1.fc25',
         u'submission_date': u'2016-11-10 15:39:25',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'erlang-fast_xml-1.1.15-1.fc25',
                    u'signed': True},
         u'build_id': 98938,
         u'expiration_date': u'2016-11-12 15:30:10',
         u'expired_date': u'2016-11-12 16:00:04',
         u'notes': u'needed for ejabberd',
         u'nvr': u'erlang-fast_xml-1.1.15-1.fc25',
         u'submission_date': u'2016-11-10 15:30:16',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'python-fedmsg-atomic-composer-2016.3-1.el7',
                    u'signed': True},
         u'build_id': 97312,
         u'expiration_date': u'2017-02-17 00:00:00',
         u'expired_date': None,
         u'notes': u'This is needed to build bodhi-2.4.0.',
         u'nvr': u'python-fedmsg-atomic-composer-2016.3-1.el7',
         u'submission_date': u'2016-10-27 15:55:34',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897},
        {u'build': {u'epoch': 0,
                    u'nvr': u'python-fedmsg-atomic-composer-2016.3-1.fc24',
                    u'signed': True},
         u'build_id': 97311,
         u'expiration_date': u'2016-10-29 00:00:00',
         u'expired_date': u'2016-10-29 00:00:23',
         u'notes': u'This is needed to build bodhi-2.3.0.',
         u'nvr': u'python-fedmsg-atomic-composer-2016.3-1.fc24',
         u'submission_date': u'2016-10-27 15:50:43',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897}],
    u'page': 1,
    u'pages': 1,
    u'rows_per_page': 20,
    u'total': 11})


EXAMPLE_QUERY_SINGLE_OVERRIDE_MUNCH = Munch({
    u'chrome': True,
    u'display_user': True,
    u'overrides': [Munch(
        {u'build': Munch({
            u'epoch': 0,
            u'nvr': u'js-tag-it-2.0-1.fc25',
            u'release_id': 15,
            u'signed': True}),
         u'build_id': 108565,
         u'expiration_date': u'2017-03-07 23:05:31',
         u'expired_date': None,
         u'notes': u'No explanation given...',
         u'nvr': u'nodejs-grunt-wrap-0.3.0-2.fc25',
         u'submission_date': u'2017-02-28 14:30:37',
         u'submitter': {u'avatar': u'AVATAR_URL',
                        u'email': u'email@example.com',
                        u'groups': [{u'name': u'packager'}],
                        u'id': 2897,
                        u'name': u'bowlofeggs',
                        u'openid': u'bowlofeggs.id.fedoraproject.org',
                        u'show_popups': True},
         u'submitter_id': 2897})],
    u'page': 1,
    u'pages': 1,
    u'rows_per_page': 20,
    u'total': 1})

# Expected output when print_resp renders EXAMPLE_QUERY_OVERRIDES_MUNCH
EXPECTED_QUERY_OVERRIDES_OUTPUT = """bowlofeggs's nodejs-grunt-wrap-0.3.0-2.fc25 override (expires 2017-03-07 14:30:36)
bowlofeggs's python-pyramid-1.5.6-3.el7 override (expires 2017-02-17 00:00:00)
bowlofeggs's erlang-esip-1.0.8-1.fc25 override (expires 2016-11-12 16:59:29)
bowlofeggs's erlang-stun-1.0.7-1.fc25 override (expires 2016-11-12 00:00:00)
bowlofeggs's erlang-iconv-1.0.2-1.fc25 override (expires 2016-11-12 00:00:00)
bowlofeggs's erlang-stringprep-1.0.6-1.fc25 override (expires 2016-11-12 00:00:00)
bowlofeggs's erlang-fast_tls-1.0.7-1.fc25 override (expires 2016-11-12 00:00:00)
bowlofeggs's erlang-fast_yaml-1.0.6-1.fc25 override (expires 2016-11-12 00:00:00)
bowlofeggs's erlang-fast_xml-1.1.15-1.fc25 override (expires 2016-11-12 15:30:10)
bowlofeggs's python-fedmsg-atomic-composer-2016.3-1.el7 override (expires 2017-02-17 00:00:00)
bowlofeggs's python-fedmsg-atomic-composer-2016.3-1.fc24 override (expires 2016-10-29 00:00:00)
11 overrides found (11 shown)
"""


EXAMPLE_UPDATE_MUNCH = Munch({
    u'date_testing': u'2016-10-06 00:55:15', u'old_updateid': None, u'pushed': True,
    u'require_testcases': True, u'date_locked': None, u'critpath': False, u'date_approved': None,
    u'stable_karma': 3, u'date_pushed': u'2016-10-21 13:23:01', u'requirements': u'',
    u'severity': u'unspecified', u'autokarma': True, u'title': u'bodhi-2.2.4-1.el7',
    u'suggest': u'unspecified', u'require_bugs': True,
    u'comments': [
        Munch({
            u'bug_feedback': [], u'user_id': 91, u'timestamp': u'2016-10-05 18:10:22',
            u'testcase_feedback': [], u'karma_critpath': 0, u'update_id': 69704, u'karma': 0,
            u'anonymous': False,
            u'text': u'This update has been submitted for testing by bowlofeggs. ', u'id': 501425,
            u'user': Munch({
                u'openid': u'bodhi.id.fedoraproject.org', u'name': u'bodhi', u'show_popups': True,
                u'id': 91, u'avatar': u'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                u'groups': [], u'email': None})}),
        Munch({
            u'bug_feedback': [], u'user_id': 91, u'timestamp': u'2016-10-05 18:10:27',
            u'testcase_feedback': [], u'karma_critpath': 0, u'update_id': 69704, u'karma': 0,
            u'anonymous': False,
            u'text': (u'This update has obsoleted [bodhi-2.2.3-1.el7]'
                      u'(https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-a0eb4cc41f), and '
                      u'has inherited its bugs and notes.'),
            u'id': 501427,
            u'user': Munch({
                u'openid': u'bodhi.id.fedoraproject.org', u'name': u'bodhi', u'show_popups': True,
                u'id': 91, u'avatar': u'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                u'groups': [], u'email': None})})],
    u'updateid': u'FEDORA-EPEL-2016-3081a94111', u'type': u'bugfix', u'close_bugs': True,
    u'meets_testing_requirements': True, u'date_submitted': u'2016-10-05 18:10:22',
    u'unstable_karma': -3, u'submitter': u'bowlofeggs',
    u'user': Munch({
        u'openid': u'bowlofeggs.id.fedoraproject.org', u'name': u'bowlofeggs', u'show_popups': True,
        u'id': 2897,
        u'avatar': u'https://seccdn.libravatar.org/avatar/some_hash',
        u'groups': [Munch({u'name': u'packager'})], u'email': u'bowlofeggs@electronsweatshop.com'}),
    u'locked': False,
    u'builds': [Munch({u'epoch': 0, u'nvr': u'bodhi-2.2.4-1.el7', u'signed': True})],
    u'date_modified': None,
    u'url': u'https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-3081a94111',
    u'test_cases': [],
    u'notes': (u'Update to 2.2.4. Release notes available at '
               u'https://github.com/fedora-infra/bodhi/releases/tag/2.2.4\n'),
    u'request': None, u'bugs': [], u'alias': u'FEDORA-EPEL-2016-3081a94111', u'status': u'stable',
    u'karma': 0,
    u'release': Munch({
        u'dist_tag': u'epel7', u'name': u'EPEL-7', u'testing_tag': u'epel7-testing',
        u'pending_stable_tag': u'epel7-pending', u'pending_signing_tag': u'epel7-signing-pending',
        u'long_name': u'Fedora EPEL 7', u'state': u'current', u'version': u'7',
        u'override_tag': u'epel7-override', u'branch': u'epel7', u'id_prefix': u'FEDORA-EPEL',
        u'pending_testing_tag': u'epel7-testing-pending', u'stable_tag': u'epel7',
        u'candidate_tag': u'epel7-testing-candidate'}), u'date_stable': u'2016-10-21 13:23:01',
    u'content_type': u'rpm'})

SINGLE_UPDATE_MUNCH = Munch({
    u'update': Munch({
        u'date_testing': u'2016-10-06 00:55:15', u'old_updateid': None, u'pushed': True,
        u'require_testcases': True, u'date_locked': None,
        u'critpath': False, u'date_approved': None,
        u'stable_karma': 3, u'date_pushed': u'2016-10-21 13:23:01', u'requirements': u'',
        u'severity': u'unspecified', u'autokarma': True, u'title': u'bodhi-2.2.4-1.el7',
        u'suggest': u'unspecified', u'require_bugs': True,
        u'comments': [
            Munch({
                u'bug_feedback': [], u'user_id': 91, u'timestamp': u'2016-10-05 18:10:22',
                u'testcase_feedback': [], u'karma_critpath': 0, u'update_id': 69704, u'karma': 0,
                u'anonymous': False,
                u'text': u'This update has been submitted for testing by bowlofeggs. ',
                u'id': 501425,
                u'user': Munch({
                    u'openid': u'bodhi.id.fedoraproject.org', u'name': u'bodhi',
                    u'show_popups': True,
                    u'id': 91, u'avatar': u'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                    u'groups': [], u'email': None})}),
            Munch({
                u'bug_feedback': [], u'user_id': 91, u'timestamp': u'2016-10-05 18:10:27',
                u'testcase_feedback': [], u'karma_critpath': 0, u'update_id': 69704, u'karma': 0,
                u'anonymous': False,
                u'text': (u'This update has obsoleted [bodhi-2.2.3-1.el7]'
                          u'(https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-a0eb4cc41f), '
                          u'and has inherited its bugs and notes.'),
                u'id': 501427,
                u'user': Munch({
                    u'openid': u'bodhi.id.fedoraproject.org', u'name': u'bodhi',
                    u'show_popups': True,
                    u'id': 91, u'avatar': u'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                    u'groups': [], u'email': None})})],
        u'updateid': u'FEDORA-EPEL-2016-3081a94111', u'type': u'bugfix', u'close_bugs': True,
        u'meets_testing_requirements': True, u'date_submitted': u'2016-10-05 18:10:22',
        u'unstable_karma': -3, u'submitter': u'bowlofeggs',
        u'user': Munch({
            u'openid': u'bowlofeggs.id.fedoraproject.org', u'name': u'bowlofeggs',
            u'show_popups': True,
            u'id': 2897,
            u'avatar': u'https://seccdn.libravatar.org/avatar/some_hash',
            u'groups': [Munch({u'name': u'packager'})],
            u'email': u'bowlofeggs@electronsweatshop.com'}),
        u'locked': False,
        u'builds': [Munch({u'epoch': 0, u'nvr': u'bodhi-2.2.4-1.el7', u'signed': True})],
        u'date_modified': None,
        u'url': u'https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-3081a94111',
        u'test_cases': [],
        u'notes': (u'Update to 2.2.4. Release notes available at '
                   u'https://github.com/fedora-infra/bodhi/releases/tag/2.2.4\n'),
        u'request': None, u'bugs': [], u'alias': u'FEDORA-EPEL-2016-3081a94111',
        u'status': u'stable', u'karma': 0,
        u'release': Munch({
            u'dist_tag': u'epel7', u'name': u'EPEL-7', u'testing_tag': u'epel7-testing',
            u'pending_stable_tag': u'epel7-pending',
            u'pending_signing_tag': u'epel7-signing-pending',
            u'long_name': u'Fedora EPEL 7', u'state': u'current', u'version': u'7',
            u'override_tag': u'epel7-override', u'branch': u'epel7', u'id_prefix': u'FEDORA-EPEL',
            u'pending_testing_tag': u'epel7-testing-pending', u'stable_tag': u'epel7',
            u'candidate_tag': u'epel7-testing-candidate'}), u'date_stable': u'2016-10-21 13:23:01',
        u'content_type': u'rpm'})})


EXAMPLE_GET_RELEASE_15 = Munch(
    {u'rows_per_page': 20, u'total': 1, u'pages': 1,
     u'releases': [
         Munch({u'dist_tag': u'f25', u'name': u'F25', u'testing_tag': u'f25-updates-testing',
                u'pending_stable_tag': u'f25-updates-pending',
                u'pending_signing_tag': u'f25-signing-pending', u'long_name': u'Fedora 25',
                u'state': u'current', u'version': u'25', u'override_tag': u'f25-override',
                u'branch': u'f25', u'id_prefix': u'FEDORA',
                u'pending_testing_tag': u'f25-updates-testing-pending',
                u'stable_tag': u'f25-updates', u'candidate_tag': u'f25-updates-candidate'})],
     u'page': 1})


# EXAMPLE_UPDATE_MUNCH is expected to generate this output in update_str
EXPECTED_UPDATE_OUTPUT = u"""================================================================================
     bodhi-2.2.4-1.el7
================================================================================
   Update ID: FEDORA-EPEL-2016-3081a94111
Content Type: rpm
     Release: Fedora EPEL 7
      Status: stable
        Type: bugfix
    Severity: unspecified
       Karma: 0
   Autokarma: True  [-3, 3]
       Notes: Update to 2.2.4. Release notes available at https://github.com
            : /fedora-infra/bodhi/releases/tag/2.2.4
   Submitter: bowlofeggs
   Submitted: 2016-10-05 18:10:22
    Comments: bodhi - 2016-10-05 18:10:22 (karma 0)
              This update has been submitted for testing by bowlofeggs.
              bodhi - 2016-10-05 18:10:27 (karma 0)
              This update has obsoleted
              [bodhi-2.2.3-1.el7](https://bodhi.fedoraproject.org/updates
              /FEDORA-EPEL-2016-a0eb4cc41f), and has inherited its bugs and
              notes.

  http://example.com/tests/updates/FEDORA-EPEL-2016-3081a94111
"""

EXPECTED_OVERRIDE_STR_OUTPUT = u"""============================================================
     js-tag-it-2.0-1.fc25
============================================================
  Submitter: bowlofeggs
  Expiration Date: 2017-03-07 23:05:31
  Notes: No explanation given...
  Expired: False
"""


EXPECTED_OVERRIDES_OUTPUT = EXPECTED_OVERRIDE_STR_OUTPUT + """

Use the following to ensure the override is active:

\t$ koji wait-repo f25-build --build=js-tag-it-2.0-1.fc25

"""

EXPECTED_EXPIRED_OVERRIDES_OUTPUT = u"""============================================================
     js-tag-it-2.0-1.fc25
============================================================
  Submitter: bowlofeggs
  Expiration Date: 2017-03-07 23:05:31
  Notes: This is an expired override
  Expired: True
"""

UNMATCHED_RESP = {"pants": "pants"}
