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
        u'candidate_tag': u'epel7-testing-candidate'}), u'date_stable': u'2016-10-21 13:23:01'})
