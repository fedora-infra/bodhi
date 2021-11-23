# Copyright © 2016-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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
    'comment': Munch({
        'bug_feedback': [], 'user_id': 2897, 'author': 'bowlofeggs',
        'timestamp': '2017-02-28 18:08:13', 'testcase_feedback': [], 'karma_critpath': 0,
        'update': Munch({
            'date_testing': '2017-02-13 22:56:06', 'pushed': True,
            'require_testcases': False, 'date_stable': None, 'critpath': False,
            'date_approved': None, 'stable_karma': 3, 'date_pushed': '2017-02-13 22:56:06',
            'requirements': '', 'severity': 'low', 'autokarma': True, 'autotime': True,
            'title': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'suggest': 'unspecified',
            'require_bugs': False, 'date_locked': None, 'type': 'newpackage',
            'close_bugs': True, 'status': 'testing', 'meets_testing_requirements': True,
            'date_submitted': '2017-02-13 17:38:43', 'unstable_karma': -3,
            'user': Munch({
                'openid': 'bowlofeggs.id.fedoraproject.org', 'name': 'bowlofeggs',
                'id': 2897,
                'avatar': 'AVATAR_URL',
                'groups': [Munch({'name': 'packager'})],
                'email': 'email@example.com'}),
            'locked': False,
            'builds': [
                Munch({'epoch': 0, 'nvr': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'signed': True})],
            'date_modified': None, 'url': 'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
            'notes': 'New package.', 'request': None,
            'bugs': [Munch({
                'bug_id': 1420605, 'security': False, 'feedback': [], 'parent': False,
                'title': ('Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping '
                          'project text files')})],
            'alias': 'FEDORA-2017-c95b33872d', 'karma': 0,
            'release': Munch({
                'dist_tag': 'f25', 'name': 'F25', 'testing_tag': 'f25-updates-testing',
                'pending_stable_tag': 'f25-updates-pending',
                'pending_signing_tag': 'f25-signing-pending', 'long_name': 'Fedora 25',
                'state': 'current', 'version': '25', 'override_tag': 'f25-override',
                'branch': 'f25', 'id_prefix': 'FEDORA',
                'pending_testing_tag': 'f25-updates-testing-pending',
                'stable_tag': 'f25-updates', 'candidate_tag': 'f25-updates-candidate',
                'package_manager': 'unspecified', 'testing_repository': None, 'eol': None})}),
        'update_id': 79733, 'karma': 0, 'text': 'i found $10000',
        'update_title': 'nodejs-grunt-wrap-0.3.0-2.fc25', 'id': 562626,
        'user': Munch({
            'openid': 'bowlofeggs.id.fedoraproject.org', 'name': 'bowlofeggs',
            'id': 2897, 'avatar': 'AVATAR_URL',
            'groups': [Munch({'name': 'packager'})], 'email': 'email@example.com'})}),
    'caveats': []})

# EXAMPLE_COMMENT_MUNCH is expected to generate this output in update_str
EXPECTED_COMMENT_OUTPUT = """The following comment was added to FEDORA-2017-c95b33872d
i found $10000
"""


EXPECTED_COMPOSE_OUTPUT = """\
================================================================================
     *EPEL-7-stable  :   2 updates (requested)
================================================================================
Content Type: rpm
     Started: 2018-03-15 17:25:22
     Updated: 2018-03-15 17:25:22

Updates:

        FEDORA-EPEL-2018-50566f0a39: uwsgi-2.0.16-1.el7
        FEDORA-EPEL-2018-328e2b8c27: qtpass-1.2.1-3.el7

"""


EXAMPLE_COMPOSE_MUNCH = Munch({
    'compose': Munch({
        'release_id': 8, 'content_type': 'rpm',
        'update_summary': [
            Munch({'alias': 'FEDORA-EPEL-2018-50566f0a39', 'title': 'uwsgi-2.0.16-1.el7'}),
            Munch({'alias': 'FEDORA-EPEL-2018-328e2b8c27', 'title': 'qtpass-1.2.1-3.el7'})],
        'error_message': None, 'request': 'stable', 'state': 'requested',
        'state_date': '2018-03-15 17:25:22', 'checkpoints': '{}',
        'release': Munch({
            'dist_tag': 'epel7', 'name': 'EPEL-7', 'testing_tag': 'epel7-testing',
            'pending_stable_tag': 'epel7-pending',
            'pending_signing_tag': 'epel7-signing-pending', 'long_name': 'Fedora EPEL 7',
            'state': 'current', 'version': '7', 'override_tag': 'epel7-override',
            'branch': 'epel7', 'id_prefix': 'FEDORA-EPEL',
            'pending_testing_tag': 'epel7-testing-pending', 'stable_tag': 'epel7',
            'candidate_tag': 'epel7-testing-candidate',
            'package_manager': 'unspecified', 'testing_repository': None,
            'eol': None}),
        'date_created': '2018-03-15 17:25:22', 'security': True})})


EXAMPLE_COMPOSES_MUNCH = Munch({
    'composes': [
        Munch({
            'release_id': 8, 'content_type': 'rpm',
            'update_summary': [
                Munch({'alias': 'FEDORA-EPEL-2018-50566f0a39', 'title': 'uwsgi-2.0.16-1.el7'}),
                Munch({'alias': 'FEDORA-EPEL-2018-328e2b8c27', 'title': 'qtpass-1.2.1-3.el7'})],
            'error_message': None, 'request': 'stable', 'state': 'requested',
            'state_date': '2018-03-15 17:25:22', 'checkpoints': '{}',
            'release': Munch({
                'dist_tag': 'epel7', 'name': 'EPEL-7', 'testing_tag': 'epel7-testing',
                'pending_stable_tag': 'epel7-pending',
                'pending_signing_tag': 'epel7-signing-pending', 'long_name': 'Fedora EPEL 7',
                'state': 'current', 'version': '7', 'override_tag': 'epel7-override',
                'branch': 'epel7', 'id_prefix': 'FEDORA-EPEL',
                'pending_testing_tag': 'epel7-testing-pending', 'stable_tag': 'epel7',
                'candidate_tag': 'epel7-testing-candidate',
                'package_manager': 'unspecified', 'testing_repository': None,
                'eol': None}),
            'date_created': '2018-03-15 17:25:22', 'security': True}),
        Munch({
            'release_id': 8, 'content_type': 'rpm',
            'update_summary': [
                Munch({'alias': 'FEDORA-EPEL-2018-32f78e466c',
                       'title': 'libmodulemd-1.1.0-1.el7'})],
            'error_message': None, 'request': 'testing', 'state': 'requested',
            'state_date': '2018-03-15 17:25:22', 'checkpoints': '{}',
            'release': Munch({
                'dist_tag': 'epel7', 'name': 'EPEL-7', 'testing_tag': 'epel7-testing',
                'pending_stable_tag': 'epel7-pending',
                'pending_signing_tag': 'epel7-signing-pending', 'long_name': 'Fedora EPEL 7',
                'state': 'current', 'version': '7', 'override_tag': 'epel7-override',
                'branch': 'epel7', 'id_prefix': 'FEDORA-EPEL',
                'pending_testing_tag': 'epel7-testing-pending', 'stable_tag': 'epel7',
                'candidate_tag': 'epel7-testing-candidate',
                'package_manager': 'unspecified', 'testing_repository': None,
                'eol': None}),
            'date_created': '2018-03-15 17:25:22', 'security': False})]})


EXAMPLE_OVERRIDE_MUNCH = Munch({
    'build_id': 108570, 'submission_date': '2017-02-28 23:05:32', 'caveats': [],
    'nvr': 'js-tag-it-2.0-1.fc25', 'expiration_date': '2017-03-07 23:05:31',
    'notes': 'No explanation given...', 'submitter_id': 2897,
    'build': Munch(
        {'epoch': 0, 'nvr': 'js-tag-it-2.0-1.fc25', 'signed': True, 'release_id': 15}),
    'expired_date': None, 'submitter': Munch({
        'openid': None, 'name': 'bowlofeggs', 'id': 2897, 'avatar': None,
        'groups': [Munch({'name': 'packager'})], 'email': 'email@example.com'})})

EXAMPLE_OVERRIDE_MUNCH_CAVEATS = Munch({
    'build_id': 108570, 'submission_date': '2017-02-28 23:05:32',
    'caveats': [Munch({'description': 'this is a caveat'})],
    'nvr': 'js-tag-it-2.0-1.fc25', 'expiration_date': '2017-03-07 23:05:31',
    'notes': 'No explanation given...', 'submitter_id': 2897,
    'build': Munch({'epoch': 0, 'nvr': 'js-tag-it-2.0-1.fc25', 'signed': True}),
    'expired_date': None, 'submitter': Munch({
        'openid': None, 'name': 'bowlofeggs', 'id': 2897, 'avatar': None,
        'groups': [Munch({'name': 'packager'})], 'email': 'email@example.com'})})

EXAMPLE_EXPIRED_OVERRIDE_MUNCH = Munch({
    'build_id': 108570, 'submission_date': '2017-02-28 23:05:32', 'caveats': [],
    'nvr': 'js-tag-it-2.0-1.fc25', 'expiration_date': '2017-03-07 23:05:31',
    'notes': 'This is an expired override', 'submitter_id': 2897,
    'build': Munch({'epoch': 0, 'nvr': 'js-tag-it-2.0-1.fc25', 'signed': True}),
    'expired_date': '2017-03-07 23:05:31', 'submitter': Munch({
        'openid': None, 'name': 'bowlofeggs', 'id': 2897, 'avatar': None,
        'groups': [Munch({'name': 'packager'})], 'email': 'email@example.com'})})

EXAMPLE_QUERY_MUNCH = Munch({
    'chrome': True,
    'display_request': True,
    'display_user': True,
    'package': None,
    'page': 1,
    'pages': 1,
    'rows_per_page': 20,
    'total': 1,
    'updates': [{
        'alias': 'FEDORA-2017-c95b33872d',
        'autokarma': True,
        'autotime': True,
        'content_type': 'rpm',
        'bugs': [{
            'bug_id': 1420605,
            'feedback': [],
            'parent': False,
            'security': False,
            'title': ('Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping project '
                      'text files')}],
        'builds': [{
            'epoch': 0,
            'nvr': 'nodejs-grunt-wrap-0.3.0-2.fc25',
            'signed': True}],
        'close_bugs': True,
        'comments': [
            {'bug_feedback': [],
             'id': 561418,
             'karma': 0,
             'karma_critpath': 0,
             'testcase_feedback': [],
             'text': 'This update has been submitted for testing by bowlofeggs. ',
             'timestamp': '2017-02-13 17:38:43',
             'update_id': 79733,
             'user': {'avatar': 'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                      'email': None,
                      'groups': [],
                      'id': 91,
                      'name': 'bodhi',
                      'openid': 'bodhi.id.fedoraproject.org'},
             'user_id': 91},
            {'bug_feedback': [],
             'id': 561619,
             'karma': 0,
             'karma_critpath': 0,
             'testcase_feedback': [],
             'text': 'This update has been pushed to testing.',
             'timestamp': '2017-02-14 00:55:18',
             'update_id': 79733,
             'user': {'avatar': 'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                      'email': None,
                      'groups': [],
                      'id': 91,
                      'name': 'bodhi',
                      'openid': 'bodhi.id.fedoraproject.org'},
             'user_id': 91},
            {'bug_feedback': [],
             'id': 562620,
             'karma': 0,
             'karma_critpath': 0,
             'testcase_feedback': [],
             'text': 'i found $100',
             'timestamp': '2017-02-28 14:47:43',
             'update_id': 79733,
             'user': {'avatar': 'AVATAR_URL',
                      'email': 'email@example.com',
                      'groups': [{'name': 'packager'}],
                      'id': 2897,
                      'name': 'bowlofeggs',
                      'openid': 'bowlofeggs.id.fedoraproject.org'},
             'user_id': 2897}],
        'critpath': False,
        'date_approved': None,
        'date_locked': None,
        'date_modified': None,
        'date_pushed': '2017-02-13 22:56:06',
        'date_stable': None,
        'date_submitted': '2017-02-13 17:38:43',
        'date_testing': '2017-02-13 22:56:06',
        'karma': 0,
        'locked': False,
        'meets_testing_requirements': True,
        'notes': 'New package.',
        'pushed': True,
        'release': {'branch': 'f25',
                    'candidate_tag': 'f25-updates-candidate',
                    'dist_tag': 'f25',
                    'id_prefix': 'FEDORA',
                    'long_name': 'Fedora 25',
                    'name': 'F25',
                    'override_tag': 'f25-override',
                    'pending_signing_tag': 'f25-signing-pending',
                    'pending_stable_tag': 'f25-updates-pending',
                    'pending_testing_tag': 'f25-updates-testing-pending',
                    'stable_tag': 'f25-updates',
                    'state': 'current',
                    'testing_tag': 'f25-updates-testing',
                    'version': '25',
                    'package_manager': 'unspecified',
                    'testing_repository': None,
                    'eol': None},
        'request': None,
        'require_bugs': False,
        'require_testcases': False,
        'requirements': '',
        'severity': 'low',
        'stable_karma': 3,
        'status': 'testing',
        'submitter': 'bowlofeggs',
        'suggest': 'unspecified',
        'test_cases': [],
        'title': 'nodejs-grunt-wrap-0.3.0-2.fc25',
        'type': 'newpackage',
        'unstable_karma': -3,
        'updateid': 'FEDORA-2017-c95b33872d',
        'url': 'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
        'user': {'avatar': 'AVATAR_URL',
                 'email': 'email@example.com',
                 'groups': [{'name': 'packager'}],
                 'id': 2897,
                 'name': 'bowlofeggs',
                 'openid': 'bowlofeggs.id.fedoraproject.org'}}]})

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
    Autotime: True
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
    'chrome': True,
    'display_request': True,
    'display_user': True,
    'package': None,
    'page': 1,
    'pages': 1,
    'rows_per_page': 20,
    'total': 2,
    'updates': [{
        'alias': 'FEDORA-2017-c95b33872d',
        'autokarma': True,
        'autotime': True,
        'content_type': 'rpm',
        'bugs': [{
            'bug_id': 1420605,
            'feedback': [],
            'parent': False,
            'security': False,
            'title': ('Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping project '
                      'text files')}],
        'builds': [{
            'epoch': 0,
            'nvr': 'nodejs-grunt-wrap-0.3.0-2.fc25',
            'signed': True}],
        'close_bugs': True,
        'comments': [],
        'critpath': False,
        'date_approved': None,
        'date_locked': None,
        'date_modified': None,
        'date_pushed': '2017-02-13 22:56:06',
        'date_stable': None,
        'date_submitted': '2017-02-13 17:38:43',
        'date_testing': '2017-02-13 22:56:06',
        'karma': 0,
        'locked': False,
        'meets_testing_requirements': True,
        'notes': 'New package.',
        'pushed': True,
        'release': {'branch': 'f25',
                    'candidate_tag': 'f25-updates-candidate',
                    'dist_tag': 'f25',
                    'id_prefix': 'FEDORA',
                    'long_name': 'Fedora 25',
                    'name': 'F25',
                    'override_tag': 'f25-override',
                    'pending_signing_tag': 'f25-signing-pending',
                    'pending_stable_tag': 'f25-updates-pending',
                    'pending_testing_tag': 'f25-updates-testing-pending',
                    'stable_tag': 'f25-updates',
                    'state': 'current',
                    'testing_tag': 'f25-updates-testing',
                    'version': '25',
                    'package_manager': 'unspecified',
                    'testing_repository': None,
                    'eol': None},
        'request': None,
        'require_bugs': False,
        'require_testcases': False,
        'requirements': '',
        'severity': 'low',
        'stable_karma': 3,
        'status': 'testing',
        'submitter': 'bowlofeggs',
        'suggest': 'unspecified',
        'test_cases': [],
        'title': 'nodejs-grunt-wrap-0.3.0-2.fc25',
        'type': 'newpackage',
        'unstable_karma': -3,
        'updateid': 'FEDORA-2017-c95b33872d',
        'url': 'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
        'user': {'avatar': 'AVATAR_URL',
                 'email': 'email@example.com',
                 'groups': [{'name': 'packager'}],
                 'id': 2897,
                 'name': 'bowlofeggs',
                 'openid': 'bowlofeggs.id.fedoraproject.org'}},
        {
        'alias': 'FEDORA-2017-c95b33872d',
        'autokarma': True,
        'autotime': True,
        'content_type': 'rpm',
        'bugs': [{
            'bug_id': 1420605,
            'feedback': [],
            'parent': False,
            'security': False,
            'title': ('Review Request: nodejs-grunt-wrap - A Grunt plugin for wrapping project '
                      'text files')}],
        'builds': [{
            'epoch': 0,
            'nvr': 'nodejs-grunt-wrap-0.3.0-2.fc25',
            'signed': True}],
        'close_bugs': True,
        'comments': [],
        'critpath': False,
        'date_approved': None,
        'date_locked': None,
        'date_modified': None,
        'date_pushed': '2017-02-13 22:56:06',
        'date_stable': None,
        'date_submitted': '2017-02-13 17:38:43',
        'date_testing': '2017-02-13 22:56:06',
        'karma': 0,
        'locked': False,
        'meets_testing_requirements': True,
        'notes': 'New package.',
        'pushed': True,
        'release': {'branch': 'f25',
                    'candidate_tag': 'f25-updates-candidate',
                    'dist_tag': 'f25',
                    'id_prefix': 'FEDORA',
                    'long_name': 'Fedora 25',
                    'name': 'F25',
                    'override_tag': 'f25-override',
                    'pending_signing_tag': 'f25-signing-pending',
                    'pending_stable_tag': 'f25-updates-pending',
                    'pending_testing_tag': 'f25-updates-testing-pending',
                    'stable_tag': 'f25-updates',
                    'state': 'current',
                    'testing_tag': 'f25-updates-testing',
                    'version': '25',
                    'package_manager': 'unspecified',
                    'testing_repository': None,
                    'eol': None},
        'request': None,
        'require_bugs': False,
        'require_testcases': False,
        'requirements': '',
        'severity': 'low',
        'stable_karma': 3,
        'status': 'testing',
        'submitter': 'bowlofeggs',
        'suggest': 'unspecified',
        'test_cases': [],
        'title': 'nodejs-grunt-wrap-0.3.0-2.fc25',
        'type': 'newpackage',
        'unstable_karma': -3,
        'updateid': 'FEDORA-2017-c95b33872d',
        'url': 'http://localhost:6543/updates/FEDORA-2017-c95b33872d',
        'user': {'avatar': 'AVATAR_URL',
                  'email': 'email@example.com',
                  'groups': [{'name': 'packager'}],
                  'id': 2897,
                  'name': 'bowlofeggs',
                  'openid': 'bowlofeggs.id.fedoraproject.org'}}]})

EXAMPLE_QUERY_OUTPUT_MULTI = """\
 nodejs-grunt-wrap-0.3.0-2.fc25           rpm        testing   2017-02-13 (17)
 nodejs-grunt-wrap-0.3.0-2.fc25           rpm        testing   2017-02-13 (17)
2 updates found (2 shown)
"""

EXAMPLE_QUERY_OVERRIDES_MUNCH = Munch({
    'chrome': True,
    'display_user': True,
    'overrides': [
        {'build': {
            'epoch': 0,
            'nvr': 'nodejs-grunt-wrap-0.3.0-2.fc25',
            'signed': True},
         'build_id': 108565,
         'expiration_date': '2017-03-07 14:30:36',
         'expired_date': None,
         'notes': 'No explanation given...',
         'nvr': 'nodejs-grunt-wrap-0.3.0-2.fc25',
         'submission_date': '2017-02-28 14:30:37',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'python-pyramid-1.5.6-3.el7',
                   'signed': True},
         'build_id': 107673,
         'expiration_date': '2017-02-17 00:00:00',
         'expired_date': None,
         'notes': 'This is needed to build bodhi-2.4.0.',
         'nvr': 'python-pyramid-1.5.6-3.el7',
         'submission_date': '2017-02-03 20:08:46',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'erlang-esip-1.0.8-1.fc25',
                   'signed': True},
         'build_id': 98946,
         'expiration_date': '2016-11-12 16:59:29',
         'expired_date': '2016-11-12 17:00:04',
         'notes': 'needed for ejabberd',
         'nvr': 'erlang-esip-1.0.8-1.fc25',
         'submission_date': '2016-11-10 16:59:35',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'erlang-stun-1.0.7-1.fc25',
                   'signed': True},
         'build_id': 98945,
         'expiration_date': '2016-11-12 00:00:00',
         'expired_date': '2016-11-12 00:00:22',
         'notes': 'This is needed for ejabberd.',
         'nvr': 'erlang-stun-1.0.7-1.fc25',
         'submission_date': '2016-11-10 16:21:53',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'erlang-iconv-1.0.2-1.fc25',
                   'signed': True},
         'build_id': 98942,
         'expiration_date': '2016-11-12 00:00:00',
         'expired_date': '2016-11-12 00:00:21',
         'notes': 'This is needed for ejabberd.',
         'nvr': 'erlang-iconv-1.0.2-1.fc25',
         'submission_date': '2016-11-10 15:45:17',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'erlang-stringprep-1.0.6-1.fc25',
                   'signed': True},
         'build_id': 98941,
         'expiration_date': '2016-11-12 00:00:00',
         'expired_date': '2016-11-12 00:00:24',
         'notes': 'This is needed for ejabberd.',
         'nvr': 'erlang-stringprep-1.0.6-1.fc25',
         'submission_date': '2016-11-10 15:43:52',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'erlang-fast_tls-1.0.7-1.fc25',
                   'signed': True},
         'build_id': 98940,
         'expiration_date': '2016-11-12 00:00:00',
         'expired_date': '2016-11-12 00:00:26',
         'notes': 'This is needed for ejabberd.',
         'nvr': 'erlang-fast_tls-1.0.7-1.fc25',
         'submission_date': '2016-11-10 15:41:09',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'erlang-fast_yaml-1.0.6-1.fc25',
                   'signed': True},
         'build_id': 98939,
         'expiration_date': '2016-11-12 00:00:00',
         'expired_date': '2016-11-12 00:00:27',
         'notes': 'This is needed for ejabberd.',
         'nvr': 'erlang-fast_yaml-1.0.6-1.fc25',
         'submission_date': '2016-11-10 15:39:25',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'erlang-fast_xml-1.1.15-1.fc25',
                   'signed': True},
         'build_id': 98938,
         'expiration_date': '2016-11-12 15:30:10',
         'expired_date': '2016-11-12 16:00:04',
         'notes': 'needed for ejabberd',
         'nvr': 'erlang-fast_xml-1.1.15-1.fc25',
         'submission_date': '2016-11-10 15:30:16',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'python-fedmsg-atomic-composer-2016.3-1.el7',
                   'signed': True},
         'build_id': 97312,
         'expiration_date': '2017-02-17 00:00:00',
         'expired_date': None,
         'notes': 'This is needed to build bodhi-2.4.0.',
         'nvr': 'python-fedmsg-atomic-composer-2016.3-1.el7',
         'submission_date': '2016-10-27 15:55:34',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897},
        {'build': {'epoch': 0,
                   'nvr': 'python-fedmsg-atomic-composer-2016.3-1.fc24',
                   'signed': True},
         'build_id': 97311,
         'expiration_date': '2016-10-29 00:00:00',
         'expired_date': '2016-10-29 00:00:23',
         'notes': 'This is needed to build bodhi-2.3.0.',
         'nvr': 'python-fedmsg-atomic-composer-2016.3-1.fc24',
         'submission_date': '2016-10-27 15:50:43',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897}],
    'page': 1,
    'pages': 1,
    'rows_per_page': 20,
    'total': 11})


EXAMPLE_QUERY_SINGLE_OVERRIDE_MUNCH = Munch({
    'chrome': True,
    'display_user': True,
    'overrides': [Munch(
        {'build': Munch({
            'epoch': 0,
            'nvr': 'js-tag-it-2.0-1.fc25',
            'release_id': 15,
            'signed': True}),
         'build_id': 108565,
         'expiration_date': '2017-03-07 23:05:31',
         'expired_date': None,
         'notes': 'No explanation given...',
         'nvr': 'nodejs-grunt-wrap-0.3.0-2.fc25',
         'submission_date': '2017-02-28 14:30:37',
         'submitter': {'avatar': 'AVATAR_URL',
                       'email': 'email@example.com',
                       'groups': [{'name': 'packager'}],
                       'id': 2897,
                       'name': 'bowlofeggs',
                       'openid': 'bowlofeggs.id.fedoraproject.org'},
         'submitter_id': 2897})],
    'page': 1,
    'pages': 1,
    'rows_per_page': 20,
    'total': 1})

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
    'date_testing': '2016-10-06 00:55:15', 'pushed': True,
    'require_testcases': True, 'date_locked': None, 'critpath': False, 'date_approved': None,
    'stable_karma': 3, 'date_pushed': '2016-10-21 13:23:01', 'requirements': '',
    'severity': 'unspecified', 'autokarma': True, 'autotime': True, 'title': 'bodhi-2.2.4-1.el7',
    'suggest': 'unspecified', 'require_bugs': True,
    'comments': [
        Munch({
            'bug_feedback': [], 'user_id': 91, 'timestamp': '2016-10-05 18:10:22',
            'testcase_feedback': [], 'karma_critpath': 0, 'update_id': 69704, 'karma': 0,
            'text': 'This update has been submitted for testing by bowlofeggs. ', 'id': 501425,
            'user': Munch({
                'openid': 'bodhi.id.fedoraproject.org', 'name': 'bodhi',
                'id': 91, 'avatar': 'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                'groups': [], 'email': None})}),
        Munch({
            'bug_feedback': [], 'user_id': 91, 'timestamp': '2016-10-05 18:10:27',
            'testcase_feedback': [], 'karma_critpath': 0, 'update_id': 69704, 'karma': 0,
            'text': ('This update has obsoleted [bodhi-2.2.3-1.el7]'
                     '(https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-a0eb4cc41f), and '
                     'has inherited its bugs and notes.'),
            'id': 501427,
            'user': Munch({
                'openid': 'bodhi.id.fedoraproject.org', 'name': 'bodhi',
                'id': 91, 'avatar': 'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                'groups': [], 'email': None})})],
    'updateid': 'FEDORA-EPEL-2016-3081a94111', 'type': 'bugfix', 'close_bugs': True,
    'meets_testing_requirements': True, 'date_submitted': '2016-10-05 18:10:22',
    'unstable_karma': -3, 'submitter': 'bowlofeggs',
    'user': Munch({
        'openid': 'bowlofeggs.id.fedoraproject.org', 'name': 'bowlofeggs',
        'id': 2897,
        'avatar': 'https://seccdn.libravatar.org/avatar/some_hash',
        'groups': [Munch({'name': 'packager'})], 'email': 'bowlofeggs@electronsweatshop.com'}),
    'locked': False,
    'builds': [Munch({'epoch': 0, 'nvr': 'bodhi-2.2.4-1.el7', 'signed': True})],
    'date_modified': None,
    'url': 'https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-3081a94111',
    'test_cases': [],
    'notes': ('Update to 2.2.4. Release notes available at '
              'https://github.com/fedora-infra/bodhi/releases/tag/2.2.4\n'),
    'request': None, 'bugs': [], 'alias': 'FEDORA-EPEL-2016-3081a94111', 'status': 'stable',
    'karma': 0,
    'release': Munch({
        'dist_tag': 'epel7', 'name': 'EPEL-7', 'testing_tag': 'epel7-testing',
        'pending_stable_tag': 'epel7-pending', 'pending_signing_tag': 'epel7-signing-pending',
        'long_name': 'Fedora EPEL 7', 'state': 'current', 'version': '7',
        'override_tag': 'epel7-override', 'branch': 'epel7', 'id_prefix': 'FEDORA-EPEL',
        'pending_testing_tag': 'epel7-testing-pending', 'stable_tag': 'epel7',
        'candidate_tag': 'epel7-testing-candidate', 'package_manager': 'unspecified',
        'testing_repository': None, 'eol': None}), 'date_stable': '2016-10-21 13:23:01',
    'content_type': 'rpm'})

SINGLE_UPDATE_MUNCH = Munch({
    'update': Munch({
        'date_testing': '2016-10-06 00:55:15', 'pushed': True,
        'require_testcases': True, 'date_locked': None,
        'critpath': False, 'date_approved': None,
        'stable_karma': 3, 'date_pushed': '2016-10-21 13:23:01', 'requirements': '',
        'severity': 'unspecified', 'autokarma': True, 'autotime': True,
        'title': 'bodhi-2.2.4-1.el7', 'suggest': 'unspecified', 'require_bugs': True,
        'comments': [
            Munch({
                'bug_feedback': [], 'user_id': 91, 'timestamp': '2016-10-05 18:10:22',
                'testcase_feedback': [], 'karma_critpath': 0, 'update_id': 69704, 'karma': 0,
                'text': 'This update has been submitted for testing by bowlofeggs. ',
                'id': 501425,
                'user': Munch({
                    'openid': 'bodhi.id.fedoraproject.org', 'name': 'bodhi',
                    'id': 91, 'avatar': 'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                    'groups': [], 'email': None})}),
            Munch({
                'bug_feedback': [], 'user_id': 91, 'timestamp': '2016-10-05 18:10:27',
                'testcase_feedback': [], 'karma_critpath': 0, 'update_id': 69704, 'karma': 0,
                'text': ('This update has obsoleted [bodhi-2.2.3-1.el7]'
                         '(https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-a0eb4cc41f), '
                         'and has inherited its bugs and notes.'),
                'id': 501427,
                'user': Munch({
                    'openid': 'bodhi.id.fedoraproject.org', 'name': 'bodhi',
                    'id': 91, 'avatar': 'https://apps.fedoraproject.org/img/icons/bodhi-24.png',
                    'groups': [], 'email': None})})],
        'updateid': 'FEDORA-EPEL-2016-3081a94111', 'type': 'bugfix', 'close_bugs': True,
        'meets_testing_requirements': True, 'date_submitted': '2016-10-05 18:10:22',
        'unstable_karma': -3, 'submitter': 'bowlofeggs',
        'user': Munch({
            'openid': 'bowlofeggs.id.fedoraproject.org', 'name': 'bowlofeggs',
            'id': 2897,
            'avatar': 'https://seccdn.libravatar.org/avatar/some_hash',
            'groups': [Munch({'name': 'packager'})],
            'email': 'bowlofeggs@electronsweatshop.com'}),
        'locked': False,
        'builds': [Munch({'epoch': 0, 'nvr': 'bodhi-2.2.4-1.el7', 'signed': True})],
        'date_modified': None,
        'url': 'https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2016-3081a94111',
        'test_cases': [],
        'notes': ('Update to 2.2.4. Release notes available at '
                  'https://github.com/fedora-infra/bodhi/releases/tag/2.2.4\n'),
        'request': None, 'bugs': [], 'alias': 'FEDORA-EPEL-2016-3081a94111',
        'status': 'stable', 'karma': 0,
        'release': Munch({
            'dist_tag': 'epel7', 'name': 'EPEL-7', 'testing_tag': 'epel7-testing',
            'pending_stable_tag': 'epel7-pending',
            'pending_signing_tag': 'epel7-signing-pending',
            'long_name': 'Fedora EPEL 7', 'state': 'current', 'version': '7',
            'override_tag': 'epel7-override', 'branch': 'epel7', 'id_prefix': 'FEDORA-EPEL',
            'pending_testing_tag': 'epel7-testing-pending', 'stable_tag': 'epel7',
            'candidate_tag': 'epel7-testing-candidate', 'package_manager': 'unspecified',
            'testing_repository': None, 'eol': None}), 'date_stable': '2016-10-21 13:23:01',
        'content_type': 'rpm'})})


EXAMPLE_GET_RELEASE_15 = Munch(
    {'rows_per_page': 20, 'total': 1, 'pages': 1,
     'releases': [
         Munch({'dist_tag': 'f25', 'name': 'F25', 'testing_tag': 'f25-updates-testing',
                'pending_stable_tag': 'f25-updates-pending',
                'pending_signing_tag': 'f25-signing-pending', 'long_name': 'Fedora 25',
                'state': 'current', 'version': '25', 'override_tag': 'f25-override',
                'branch': 'f25', 'id_prefix': 'FEDORA',
                'pending_testing_tag': 'f25-updates-testing-pending',
                'stable_tag': 'f25-updates', 'candidate_tag': 'f25-updates-candidate',
                'package_manager': 'unspecified', 'testing_repository': None, 'eol': None})],
     'page': 1})


# EXAMPLE_UPDATE_MUNCH is expected to generate this output in update_str
EXPECTED_UPDATE_OUTPUT = """================================================================================
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
    Autotime: True
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

EXPECTED_OVERRIDE_STR_OUTPUT = """============================================================
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

EXPECTED_EXPIRED_OVERRIDES_OUTPUT = """============================================================
     js-tag-it-2.0-1.fc25
============================================================
  Submitter: bowlofeggs
  Expiration Date: 2017-03-07 23:05:31
  Notes: This is an expired override
  Expired: True
"""

EXAMPLE_RELEASE_MUNCH = Munch({
    'dist_tag': 'f27', 'testing_tag': 'f27-updates-testing', 'branch': 'f27',
    'pending_stable_tag': 'f27-updates-pending', 'pending_signing_tag': 'f27-signing-pending',
    'long_name': 'Fedora 27', 'state': 'pending', 'version': '27', 'name': 'F27',
    'override_tag': 'f27-override', 'id_prefix': 'FEDORA', 'composed_by_bodhi': True,
    'pending_testing_tag': 'f27-updates-testing-pending', 'stable_tag': 'f27-updates',
    'candidate_tag': 'f27-updates-candidate', 'mail_template': 'fedora_errata_template',
    'create_automatic_updates': False, 'package_manager': 'unspecified',
    'testing_repository': None, 'eol': None})


EXPECTED_RELEASE_OUTPUT = """Saved release:
  Name:                     F27
  Long Name:                Fedora 27
  Version:                  27
  Branch:                   f27
  ID Prefix:                FEDORA
  Dist Tag:                 f27
  Stable Tag:               f27-updates
  Testing Tag:              f27-updates-testing
  Candidate Tag:            f27-updates-candidate
  Pending Signing Tag:      f27-signing-pending
  Pending Testing Tag:      f27-updates-testing-pending
  Pending Stable Tag:       f27-updates-pending
  Override Tag:             f27-override
  State:                    pending
  Email Template:           fedora_errata_template
  Composed by Bodhi:        True
  Create Automatic Updates: False
  Package Manager:          unspecified
  Testing Repository:       None
  End of Life:              None
"""

EXAMPLE_ARCHIVED_RELEASE_MUNCH = Munch({
    'composes': [], 'dist_tag': 'f26', 'name': 'F26',
    'testing_tag': 'f26-updates-testing', 'pending_stable_tag': 'f26-updates-pending',
    'mail_template': 'fedora_errata_template', 'long_name': 'Fedora 26',
    'state': 'archived', 'version': '26', 'id_prefix': 'FEDORA', 'branch': 'f26',
    'pending_signing_tag': 'f26-signing-pending',
    'pending_testing_tag': 'f26-updates-testing-pending',
    'candidate_tag': 'f26-updates-candidate', 'stable_tag': 'f26-updates',
    'override_tag': 'f26-override', 'composed_by_bodhi': True,
    'package_manager': 'unspecified', 'testing_repository': None, 'eol': None,
})

EXAMPLE_CURRENT_RELEASE_MUNCH = Munch({
    'composes': [], 'dist_tag': 'f28', 'name': 'F28',
    'testing_tag': 'f28-updates-testing', 'pending_stable_tag': 'f28-updates-pending',
    'mail_template': 'fedora_errata_template', 'long_name': 'Fedora 28',
    'state': 'current', 'version': '28', 'id_prefix': 'FEDORA', 'branch': 'f28',
    'pending_signing_tag': 'f28-signing-pending',
    'pending_testing_tag': 'f28-updates-testing-pending',
    'candidate_tag': 'f28-updates-candidate', 'stable_tag': 'f28-updates',
    'override_tag': 'f28-override', 'composed_by_bodhi': True,
    'package_manager': 'unspecified', 'testing_repository': None, 'eol': None,
})

EXAMPLE_PENDING_RELEASE_MUNCH = Munch({
    'composes': [], 'dist_tag': 'f29', 'name': 'F29',
    'testing_tag': 'f29-updates-testing', 'pending_stable_tag': 'f29-updates-pending',
    'mail_template': 'fedora_errata_template', 'long_name': 'Fedora 29',
    'state': 'pending', 'version': '29', 'id_prefix': 'FEDORA', 'branch': 'f29',
    'pending_signing_tag': 'f29-signing-pending',
    'pending_testing_tag': 'f29-updates-testing-pending',
    'candidate_tag': 'f29-updates-candidate', 'stable_tag': 'f29-updates',
    'override_tag': 'f29-override', 'composed_by_bodhi': True,
    'package_manager': 'unspecified', 'testing_repository': None, 'eol': None,
})

EXAMPLE_FROZEN_RELEASE_MUNCH = Munch({
    'composes': [], 'dist_tag': 'f30', 'name': 'F30',
    'testing_tag': 'f30-updates-testing', 'pending_stable_tag': 'f30-updates-pending',
    'mail_template': 'fedora_errata_template', 'long_name': 'Fedora 30',
    'state': 'frozen', 'version': '30', 'id_prefix': 'FEDORA', 'branch': 'f30',
    'pending_signing_tag': 'f30-signing-pending',
    'pending_testing_tag': 'f30-updates-testing-pending',
    'candidate_tag': 'f30-updates-candidate', 'stable_tag': 'f30-updates',
    'override_tag': 'f30-override', 'composed_by_bodhi': True,
    'package_manager': 'unspecified', 'testing_repository': None, 'eol': None,
})

EXAMPLE_RELEASE_MUNCH_NO_ARCHIVED = Munch({
    'rows_per_page': 20, 'total': 3, 'pages': 1,
    'releases': [
        EXAMPLE_CURRENT_RELEASE_MUNCH,
        EXAMPLE_PENDING_RELEASE_MUNCH,
        EXAMPLE_FROZEN_RELEASE_MUNCH,
    ]
})

EXAMPLE_RELEASE_MUNCH_WITH_ARCHIVED = Munch({
    'rows_per_page': 20, 'total': 3, 'pages': 1,
    'releases': [
        EXAMPLE_ARCHIVED_RELEASE_MUNCH,
        EXAMPLE_CURRENT_RELEASE_MUNCH,
        EXAMPLE_PENDING_RELEASE_MUNCH,
    ]
})

EXPECTED_PENDING_RELEASES_LIST_OUTPUT = """pending:
  Name:                F29
"""

EXPECTED_ARCHIVED_RELEASES_LIST_OUTPUT = """archived:
  Name:                F26
"""

EXPECTED_CURRENT_RELEASES_LIST_OUTPUT = """current:
  Name:                F28
"""

EXPECTED_FROZEN_RELEASES_LIST_OUTPUT = """frozen:
  Name:                F30
"""


UNMATCHED_RESP = {"pants": "pants"}
