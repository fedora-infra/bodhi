# Copyright (C) 2018-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Unit tests for the errata message schemas."""


from bodhi.messages.schemas.errata import BuildV1, ErrataPublishV1, ReleaseV1, UpdateV1, UserV1
from .utils import check_message


class TestErrataMessage:
    """A set of unit tests for classes in :py:mod:`bodhi_messages.schemas.errata`"""

    def test_publish_v1(self):
        """Test an ErrataPublishV1."""
        expected = {
            "topic": "bodhi.errata.publish",
            "summary": "This is the subject of the errata email",
            "__str__": "This is the body of the errata email",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-4cc36fafbb",
            "agent_avatar": (
                'https://seccdn.libravatar.org/avatar/'
                'a9bfa08eb2cdbfc3f0c22150b53985ea4489d288d9618b53b7d039c44e0f829d?s=64&d=retro'),
            "usernames": ['test_submitter'],
            "packages": ["tzdata"],
            'agent': 'test_submitter',
            'update': UpdateV1(
                "FEDORA-2019-4cc36fafbb",
                [BuildV1('tzdata-2014i-1.fc19')], UserV1('test_submitter'),
                'pending', 'testing', ReleaseV1('F19')),
        }
        msg = ErrataPublishV1(
            body={
                "subject": "This is the subject of the errata email",
                "body": "This is the body of the errata email",
                "update": {
                    "alias": "FEDORA-2019-4cc36fafbb",
                    "close_bugs": True,
                    "pushed": False,
                    "require_testcases": True,
                    "critpath": False,
                    "stable_karma": 3,
                    "date_pushed": None,
                    "severity": "unspecified",
                    "title": "tzdata-2014i-1.fc19",
                    "suggest": "unspecified",
                    "require_bugs": True,
                    "comments": [
                        {
                            "bug_feedback": [],
                            "user_id": 1681,
                            "timestamp": "2015-01-28 03:02:44",
                            "testcase_feedback": [],
                            "karma_critpath": 0,
                            "update": 54046,
                            "update_id": 54046,
                            "karma": 0,
                            "anonymous": False,
                            "text": "ralph edited this update. ",
                            "id": 484236,
                            "user": {
                                "buildroot_overrides": [],
                                "name": "bodhi",
                                "avatar": None
                            }
                        }
                    ],
                    "date_approved": None,
                    "type": "enhancement",
                    "status": "pending",
                    "date_submitted": "2014-10-29 20:02:57",
                    "unstable_karma": -3,
                    "user": {
                        "buildroot_overrides": [],
                        "name": "test_submitter",
                        "avatar": None
                    },
                    "locked": False,
                    "builds": [
                        {
                            "override": None,
                            "nvr": "tzdata-2014i-1.fc19"
                        }
                    ],
                    "date_modified": "2015-01-28 03:02:55",
                    "notes": "the update notes go here...",
                    "request": "testing",
                    "bugs": [],
                    "karma": 0,
                    "release": {
                        "dist_tag": "f19",
                        "name": "F19",
                        "testing_tag": "f19-updates-testing",
                        "pending_stable_tag": "f19-updates-pending",
                        "long_name": "Fedora 19",
                        "state": "disabled",
                        "version": None,
                        "override_tag": "f19-override",
                        "branch": None,
                        "id_prefix": "FEDORA",
                        "pending_testing_tag": "f19-updates-testing-pending",
                        "stable_tag": "f19-updates",
                        "candidate_tag": "f19-updates-candidate"
                    }
                }
            }
        )
        check_message(msg, expected)
