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
"""Unit tests for the update message schemas."""


from bodhi.messages.schemas.base import BuildV1, ReleaseV1, UpdateV1, UserV1
from bodhi.messages.schemas.update import (UpdateCommentV1,
                                           UpdateCompleteStableV1,
                                           UpdateCompleteTestingV1,
                                           UpdateEditV1, UpdateEjectV1,
                                           UpdateKarmaThresholdV1,
                                           UpdateReadyForTestingV1,
                                           UpdateReadyForTestingV2,
                                           UpdateRequestObsoleteV1,
                                           UpdateRequestRevokeV1,
                                           UpdateRequestStableV1,
                                           UpdateRequestTestingV1,
                                           UpdateRequestUnpushV1,
                                           UpdateRequirementsMetStableV1)

from .utils import check_message


class TestUpdateMessage:
    """A set of unit tests for classes in :py:mod:`bodhi_messages.schemas.update`"""

    def test_eject_v1(self):
        expected = {
            "topic": "bodhi.update.eject",
            "summary": (
                "mbooth's xstream-1.4.11.1-2.fc30 bodhi update "
                "was ejected from the test_repo mash. Reason: \"some reason\""
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-2b055f8870",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "20652954adacfd9f6e26536bbcf3b5fbc850dc61f8a2e67c5bfbc6e345032976"
                "?s=64&d=retro"
            ),
            "usernames": ["mbooth", 'mohanboddu'],
            "packages": ["xstream"],
            'repo': 'test_repo',
            'update': UpdateV1('FEDORA-2019-2b055f8870', [BuildV1('xstream-1.4.11.1-2.fc30')],
                               UserV1('mbooth'), 'testing', None, ReleaseV1('F30'))
        }
        msg = UpdateEjectV1(
            body={
                "agent": "mohanboddu",
                "update": {
                    "alias": "FEDORA-2019-2b055f8870",
                    "builds": [{
                        "release_id": 28, "nvr": "xstream-1.4.11.1-2.fc30", "signed": True,
                        "epoch": 0, "ci_url": None, "type": "rpm"}],
                    "locked": True,
                    "title": "xstream-1.4.11.1-2.fc30",
                    "release": {"name": "F30"},
                    'request': None,
                    "status": "testing",
                    'user': {'name': 'mbooth'}
                },
                "reason": "some reason",
                "release": {
                    "dist_tag": "fc30",
                    "long_name": "Fedora 30",
                    "name": "F30",
                },
                "request": "testing",
                "repo": "test_repo",
            }
        )
        check_message(msg, expected)

    def test_complete_stable_v1(self):
        expected = {
            "topic": "bodhi.update.complete.stable",
            "summary": (
                "eclipseo's golang-github-SAP-go-hdb-0.14.1-1.fc29 t… bodhi update "
                "completed push to stable"
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-d64d0caab3",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "20652954adacfd9f6e26536bbcf3b5fbc850dc61f8a2e67c5bfbc6e345032976"
                "?s=64&d=retro"
            ),
            "usernames": ["eclipseo", 'mohanboddu'],
            "packages": ["golang-github-SAP-go-hdb", 'texworks'],
            'update': UpdateV1(
                'FEDORA-2019-d64d0caab3',
                [BuildV1('golang-github-SAP-go-hdb-0.14.1-1.fc29'),
                 BuildV1('texworks-0.6.3-1.fc29')],
                UserV1('eclipseo'), 'stable', None, ReleaseV1('F29'))
        }
        msg = UpdateCompleteStableV1(
            body={
                "update": {
                    "alias": "FEDORA-2019-d64d0caab3",
                    "builds": [{"nvr": "golang-github-SAP-go-hdb-0.14.1-1.fc29"},
                               {'nvr': 'texworks-0.6.3-1.fc29'}],
                    "title": "fedmsg-0.2.7-2.el6",
                    'release': {"name": "F29"},
                    'request': None,
                    "status": "stable",
                    "user": {"name": "eclipseo"}
                },
                'agent': 'mohanboddu'
            }
        )
        check_message(msg, expected)

    def test_complete_testing_v1(self):
        expected = {
            "topic": "bodhi.update.complete.testing",
            "summary": (
                "eclipseo's golang-github-SAP-go-hdb-0.14.1-1.fc29 t… bodhi update "
                "completed push to testing"
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-d64d0caab3",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "20652954adacfd9f6e26536bbcf3b5fbc850dc61f8a2e67c5bfbc6e345032976"
                "?s=64&d=retro"
            ),
            "usernames": ["eclipseo", 'mohanboddu'],
            "packages": ["golang-github-SAP-go-hdb", 'texworks'],
            'update': UpdateV1(
                'FEDORA-2019-d64d0caab3',
                [BuildV1('golang-github-SAP-go-hdb-0.14.1-1.fc29'),
                 BuildV1('texworks-0.6.3-1.fc29')],
                UserV1('eclipseo'), 'testing', None, ReleaseV1('F29'))
        }
        msg = UpdateCompleteTestingV1(
            body={
                "update": {
                    "alias": "FEDORA-2019-d64d0caab3",
                    "builds": [{"nvr": "golang-github-SAP-go-hdb-0.14.1-1.fc29"},
                               {'nvr': 'texworks-0.6.3-1.fc29'}],
                    "title": "fedmsg-0.2.7-2.el6",
                    'release': {"name": "F29"},
                    'request': None,
                    "status": "testing",
                    "user": {"name": "eclipseo"}
                },
                'agent': 'mohanboddu'
            }
        )
        check_message(msg, expected)

    def test_ready_for_testing_v1(self):
        expected = {
            "topic": "bodhi.update.status.testing.koji-build-group.build.complete",
            "summary": (
                "BaseOS CI's libselinux-2.8-6.fc29.x86_64 libsepol-2.… bodhi update "
                "is ready for testing"
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-d64d0caab3",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "20652954adacfd9f6e26536bbcf3b5fbc850dc61f8a2e67c5bfbc6e345032976"
                "?s=64&d=retro"
            ),
            "usernames": ["mohanboddu", "plautrba"],
            "packages": ["libselinux", "libsepol"],
        }
        msg = UpdateReadyForTestingV1(
            body={
                "contact": {
                    "name": "BaseOS CI",
                    "team": "BaseOS",
                    "url": "https://somewhere.com",
                    "docs": "https://somewhere.com/user-documentation",
                    "irc": "#baseosci",
                    "email": "baseos-ci@somewhere.com"
                },
                "artifact": {
                    "type": "koji-build-group",
                    "id": "FEDORA-2019-d64d0caab3",
                    "repository": "https://bodhi.fp.o/updates/FEDORA-2019-d64d0caab3",
                    "builds":
                        [{
                            "type": "koji-build",
                            "id": 14546275,
                            "task_id": 14546276,
                            "issuer": "plautrba",
                            "component": "libselinux",
                            "nvr": "libselinux-2.8-6.fc29.x86_64",
                            "scratch": False,
                        }, {
                            "type": "koji-build",
                            "id": 14546278,
                            "task_id": None,
                            "issuer": "plautrba",
                            "component": "libsepol",
                            "nvr": "libsepol-2.8-3.fc29.x86_64",
                            "scratch": False,
                        }],
                    "release": "f29",
                },
                "generated_at": "2019-10-22 13:08:10.222602",
                "version": "0.2.2",
                "agent": "mohanboddu",
            }
        )
        check_message(msg, expected)

    def test_ready_for_testing_v2(self):
        expected = {
            "topic": "bodhi.update.status.testing.koji-build-group.build.complete",
            "summary": (
                "BaseOS CI's libselinux-2.8-6.fc29.x86_64 libsepol-2.… bodhi update "
                "is ready for testing"
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-d64d0caab3",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "20652954adacfd9f6e26536bbcf3b5fbc850dc61f8a2e67c5bfbc6e345032976"
                "?s=64&d=retro"
            ),
            "usernames": ["mohanboddu", "plautrba"],
            "packages": ["libselinux", "libsepol"],
        }
        msg = UpdateReadyForTestingV2(
            body={
                "contact": {
                    "name": "BaseOS CI",
                    "team": "BaseOS",
                    "url": "https://somewhere.com",
                    "docs": "https://somewhere.com/user-documentation",
                    "irc": "#baseosci",
                    "email": "baseos-ci@somewhere.com"
                },
                "artifact": {
                    "type": "koji-build-group",
                    "id": "FEDORA-2019-d64d0caab3",
                    "repository": "https://bodhi.fp.o/updates/FEDORA-2019-d64d0caab3",
                    "builds":
                        [{
                            "type": "koji-build",
                            "id": 14546275,
                            "task_id": 14546276,
                            "issuer": "plautrba",
                            "component": "libselinux",
                            "nvr": "libselinux-2.8-6.fc29.x86_64",
                            "scratch": False,
                        }, {
                            "type": "koji-build",
                            "id": 14546278,
                            "task_id": None,
                            "issuer": "plautrba",
                            "component": "libsepol",
                            "nvr": "libsepol-2.8-3.fc29.x86_64",
                            "scratch": False,
                        }],
                    "release": "f29",
                },
                "update": {
                    "alias": "FEDORA-2019-d64d0caab3",
                    "builds": [{"nvr": "libselinux-2.8-6.fc29.x86_64"},
                               {"nvr": "libsepol-2.8-3.fc29.x86_64"}],
                    "title": "flibselinux-2.8-6.fc29",
                    'release': {"name": "F29"},
                    'request': None,
                    "status": "testing",
                    "user": {"name": "plautrba"}
                },
                "generated_at": "2019-10-22 13:08:10.222602",
                "version": "0.2.2",
                "agent": "mohanboddu",
            }
        )
        check_message(msg, expected)

    def test_request_testing_v1_multiple(self):
        expected = {
            "topic": "bodhi.update.request.testing",
            "summary": "lmacken submitted FEDORA-2019-f1ca3c00e5 to testing",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-f1ca3c00e5",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "203f6cb95b44b5d38aa21425b066dd522d3e19d8919cf4b339f29e0ea7f03e9b"
                "?s=64&d=retro"
            ),
            "usernames": ["hadess", "lmacken"],
            "packages": ["gnome-settings-daemon", "control-center"],
            'update': UpdateV1(
                'FEDORA-2019-f1ca3c00e5',
                [BuildV1('gnome-settings-daemon-3.6.1-1.fc18'),
                 BuildV1('control-center-3.6.1-1.fc18')],
                UserV1('hadess'), 'pending', 'testing', ReleaseV1('F18'))
        }
        msg = UpdateRequestTestingV1(
            body={
                'agent': 'lmacken',
                "update": {
                    'alias': 'FEDORA-2019-f1ca3c00e5',
                    "status": "pending",
                    "critpath": False,
                    "stable_karma": 3,
                    "date_pushed": None,
                    'user': {'name': 'hadess'},
                    "title": (
                        "gnome-settings-daemon-3.6.1-1.fc18,"
                        "control-center-3.6.1-1.fc18"
                    ),
                    "comments": [
                        {
                            "group": None,
                            "author": "bodhi",
                            "text": "This update has been submitted for "
                            "testing by hadess. ",
                            "karma": 0,
                            "anonymous": False,
                            "timestamp": 1349718539.0,
                            "update_title": (
                                "gnome-settings-daemon-3.6.1-1.fc18,"
                                "control-center-3.6.1-1.fc18"
                            )
                        }
                    ],
                    "type": "bugfix",
                    "close_bugs": True,
                    "date_submitted": 1349718534.0,
                    "unstable_karma": -3,
                    "release": {
                        "dist_tag": "f18",
                        "locked": True,
                        "long_name": "Fedora 18",
                        "name": "F18",
                        "id_prefix": "FEDORA"
                    },
                    "builds": [
                        {
                            "nvr": "gnome-settings-daemon-3.6.1-1.fc18",
                            "package": {
                                "suggest_reboot": False,
                                "committers": [
                                    "hadess",
                                    "ofourdan",
                                    "mkasik",
                                    "cosimoc"
                                ],
                                "name": "gnome-settings-daemon"
                            }
                        }, {
                            "nvr": "control-center-3.6.1-1.fc18",
                            "package": {
                                "suggest_reboot": False,
                                "committers": [
                                    "ctrl-center-team",
                                    "ofourdan",
                                    "ssp",
                                    "ajax",
                                    "alexl",
                                    "jrb",
                                    "mbarnes",
                                    "caolanm",
                                    "davidz",
                                    "mclasen",
                                    "rhughes",
                                    "hadess",
                                    "johnp",
                                    "caillon",
                                    "whot",
                                    "rstrode"
                                ],
                                "name": "control-center"
                            }
                        }
                    ],
                    "date_modified": None,
                    "notes": (
                        "This update fixes numerous bugs in the new Input "
                        "Sources support, the Network panel and adds a help "
                        "screen accessible via Wacom tablets's buttons."
                    ),
                    "request": "testing",
                    "bugs": [],
                    "critpath_approved": False,
                    "karma": 0,
                }
            }
        )
        check_message(msg, expected)

    def test_request_unpush_v1(self):
        """Test a request unpush message."""
        expected = {
            "topic": "bodhi.update.request.unpush",
            "summary": "ralph unpushed FEDORA-2019-8da6360454",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-8da6360454",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "9c9f7784935381befc302fe3c814f9136e7a33953d0318761669b8643f4df55c"
                "?s=64&d=retro"
            ),
            "usernames": ["ralph"],
            "packages": ["python-operator-courier"],
            'update': UpdateV1(
                'FEDORA-2019-8da6360454', [BuildV1('python-operator-courier-1.2.0-1.fc28')],
                UserV1('ralph'), 'unpushed', None, ReleaseV1('F28'))
        }
        msg = UpdateRequestUnpushV1(
            body={
                'agent': 'ralph',
                'update': {
                    "alias": "FEDORA-2019-8da6360454",
                    "builds": [{'nvr': 'python-operator-courier-1.2.0-1.fc28'}],
                    "release": {"name": "F28"},
                    'request': None,
                    "status": "unpushed",
                    "user": {"name": "ralph"}
                },
            }
        )
        check_message(msg, expected)

    def test_request_obsolete_v1(self):
        expected = {
            "topic": "bodhi.update.request.obsolete",
            "summary": "lmacken obsoleted FEDORA-2019-d64d0caab3",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-d64d0caab3",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "203f6cb95b44b5d38aa21425b066dd522d3e19d8919cf4b339f29e0ea7f03e9b"
                "?s=64&d=retro"
            ),
            "usernames": ['eclipseo', "lmacken"],
            "packages": ["golang-github-SAP-go-hdb"],
            'update': UpdateV1(
                'FEDORA-2019-d64d0caab3', [BuildV1('golang-github-SAP-go-hdb-0.14.1-1.fc29')],
                UserV1('eclipseo'), 'testing', None, ReleaseV1('F29'))
        }
        msg = UpdateRequestObsoleteV1(
            body={
                'agent': 'lmacken',
                'update': {
                    "alias": "FEDORA-2019-d64d0caab3",
                    "builds": [{"nvr": "golang-github-SAP-go-hdb-0.14.1-1.fc29"}],
                    "title": "golang-github-SAP-go-hdb-0.14.1-1.fc29",
                    'release': {"name": "F29"},
                    'request': None,
                    "status": "testing",
                    "user": {"name": "eclipseo"}
                },
            }
        )
        check_message(msg, expected)

    def test_request_stable_v1(self):
        expected = {
            "topic": "bodhi.update.request.stable",
            "summary": "lmacken submitted FEDORA-2019-d64d0caab3 to stable",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-d64d0caab3",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "203f6cb95b44b5d38aa21425b066dd522d3e19d8919cf4b339f29e0ea7f03e9b"
                "?s=64&d=retro"
            ),
            "usernames": ['eclipseo', "lmacken"],
            "packages": ["golang-github-SAP-go-hdb"],
            'update': UpdateV1(
                'FEDORA-2019-d64d0caab3', [BuildV1('golang-github-SAP-go-hdb-0.14.1-1.fc29')],
                UserV1('eclipseo'), 'testing', 'stable', ReleaseV1('F29'))
        }
        msg = UpdateRequestStableV1(
            body={
                'agent': 'lmacken',
                'update': {
                    "alias": "FEDORA-2019-d64d0caab3",
                    "builds": [{"nvr": "golang-github-SAP-go-hdb-0.14.1-1.fc29"}],
                    "release": {"name": "F29"},
                    'request': 'stable',
                    "status": "testing",
                    "user": {"name": "eclipseo"}
                },
            }
        )
        check_message(msg, expected)

    def test_request_revoke_v1(self):
        expected = {
            "topic": "bodhi.update.request.revoke",
            "summary": "lmacken revoked FEDORA-2019-d64d0caab3",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-d64d0caab3",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "203f6cb95b44b5d38aa21425b066dd522d3e19d8919cf4b339f29e0ea7f03e9b"
                "?s=64&d=retro"
            ),
            "usernames": ['eclipseo', "lmacken"],
            "packages": ["golang-github-SAP-go-hdb"],
            'update': UpdateV1(
                'FEDORA-2019-d64d0caab3', [BuildV1('golang-github-SAP-go-hdb-0.14.1-1.fc29')],
                UserV1('eclipseo'), 'testing', None, ReleaseV1('F29'))
        }
        msg = UpdateRequestRevokeV1(
            body={
                'agent': 'lmacken',
                'update': {
                    "alias": "FEDORA-2019-d64d0caab3",
                    "builds": [{"nvr": "golang-github-SAP-go-hdb-0.14.1-1.fc29"}],
                    "release": {"name": "F29"},
                    'request': None,
                    "status": "testing",
                    "user": {"name": "eclipseo"}
                },
            }
        )
        check_message(msg, expected)

    def test_request_testing_v1(self):
        expected = {
            "topic": "bodhi.update.request.testing",
            "summary": "eclipseo submitted FEDORA-2019-f1ca3c00e5 to testing",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-f1ca3c00e5",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "899e8719059bf1b2d3aba96e3e276f72f24f18a9e1f4fbfa7a331995a628e760"
                "?s=64&d=retro"
            ),
            "usernames": ["eclipseo"],
            "packages": ["golang-github-Masterminds-semver"],
            'update': UpdateV1(
                'FEDORA-2019-f1ca3c00e5',
                [BuildV1('golang-github-Masterminds-semver-2.0.0-0.1.20190319git3c92f33.fc29')],
                UserV1('eclipseo'), 'pending', 'testing', ReleaseV1('F29'))
        }
        msg = UpdateRequestTestingV1(
            body={
                'agent': 'eclipseo',
                'update': {
                    "alias": "FEDORA-2019-f1ca3c00e5",
                    "builds": [{
                        "nvr": "golang-github-Masterminds-semver-2.0.0-0.1.20190319git3c92f33.fc29"
                    }],
                    "release": {"name": "F29"},
                    'request': 'testing',
                    "status": "pending",
                    "user": {"name": "eclipseo"}
                },
            }
        )
        check_message(msg, expected)

    def test_requirements_met_stable_v1(self):
        expected = {
            "topic": "bodhi.update.requirements_met.stable",
            "summary": "FEDORA-2019-f1ca3c00e5 has met stable testing requirements",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-f1ca3c00e5",
            "agent_avatar": None,
            "usernames": ["eclipseo"],
            "packages": ["golang-github-Masterminds-semver"],
            'update': UpdateV1(
                'FEDORA-2019-f1ca3c00e5',
                [BuildV1('golang-github-Masterminds-semver-2.0.0-0.1.20190319git3c92f33.fc29')],
                UserV1('eclipseo'), 'pending', 'testing', ReleaseV1('F29'))
        }
        msg = UpdateRequirementsMetStableV1(
            body={
                'update': {
                    "alias": "FEDORA-2019-f1ca3c00e5",
                    "builds": [{
                        "nvr": "golang-github-Masterminds-semver-2.0.0-0.1.20190319git3c92f33.fc29"
                    }],
                    "release": {"name": "F29"},
                    'request': 'testing',
                    "status": "pending",
                    "user": {"name": "eclipseo"}
                },
            }
        )
        check_message(msg, expected)

    def test_comment_v1(self):
        expected = {
            "topic": "bodhi.update.comment",
            "summary": "ralph commented on bodhi update FEDORA-EPEL-2019-f2d195dada (karma: -1)",
            "__str__": (
                "Can you believe how much testing we're doing? "
                "/cc @codeblock.\n"
                "Nothing from this e-mail should match the regex: test@example.com"
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2019-f2d195dada",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "9c9f7784935381befc302fe3c814f9136e7a33953d0318761669b8643f4df55c"
                "?s=64&d=retro"
            ),
            "usernames": ["codeblock", "ralph", "tdawson"],
            "packages": ['abrt-addon-python3', 'asciinema'],
            'karma': -1,
            'user': UserV1('ralph'),
            'update': UpdateV1(
                'FEDORA-EPEL-2019-f2d195dada',
                [BuildV1("abrt-addon-python3-2.1.11-50.el7"), BuildV1("asciinema-1.4.0-2.el7")],
                UserV1('tdawson'), 'pending', 'testing', ReleaseV1('F29')),
            'agent': 'ralph',
        }
        msg = UpdateCommentV1(
            body={
                "comment": {
                    "karma": -1,
                    "text": "Can you believe how much testing we're doing?"
                            " /cc @codeblock.\n"
                            "Nothing from this e-mail should match the regex: test@example.com",
                    "timestamp": "2019-03-18 16:54:48",
                    "update": {
                        "alias": "FEDORA-EPEL-2019-f2d195dada",
                        'builds': [{'nvr': 'abrt-addon-python3-2.1.11-50.el7'},
                                   {'nvr': 'asciinema-1.4.0-2.el7'}],
                        'status': 'pending',
                        "release": {"name": "F29"},
                        'request': 'testing',
                        'user': {"name": "tdawson"}},
                    'user': {'name': 'ralph'}
                }
            }
        )
        check_message(msg, expected)

    def test_edit_v1(self):
        expected = {
            "topic": "bodhi.update.edit",
            "summary": "ralph edited FEDORA-2019-7dbbb74a13",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-2019-7dbbb74a13",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "9c9f7784935381befc302fe3c814f9136e7a33953d0318761669b8643f4df55c"
                "?s=64&d=retro"
            ),
            "new_bugs": [1708925, 1706626],
            "usernames": ["ralph"],
            "packages": ["tzdata"],
            'update': UpdateV1('FEDORA-2019-7dbbb74a13', [BuildV1('tzdata-2014i-1.fc19')],
                               UserV1('ralph'), 'pending', 'testing', ReleaseV1('F19'))
        }
        msg = UpdateEditV1(
            body={
                "new_bugs": [1708925, 1706626],
                "update": {
                    "close_bugs": True,
                    "pushed": False,
                    "require_testcases": True,
                    "critpath": False,
                    "stable_karma": 3,
                    "date_pushed": None,
                    "requirements": "rpmlint",
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
                        "name": "ralph",
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
                    "alias": 'FEDORA-2019-7dbbb74a13',
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
                },
                "agent": "ralph"
            }
        )
        check_message(msg, expected)

    def test_karma_threshold_v1(self):
        expected = {
            "topic": "bodhi.update.karma.threshold.reach",
            "summary": "FEDORA-EPEL-2015-0238 reached the stable karma threshold",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/updates/FEDORA-EPEL-2015-0238",
            "agent_avatar": None,
            "usernames": ['ralph'],
            "packages": ["tzdata"],
            'update': UpdateV1('FEDORA-EPEL-2015-0238', [BuildV1('tzdata-2014i-1.fc19')],
                               UserV1('ralph'), 'pending', 'testing', ReleaseV1('F19')),
            'status': 'stable'
        }
        msg = UpdateKarmaThresholdV1(
            body={
                "status": "stable",
                "update": {
                    "close_bugs": True,
                    "pushed": False,
                    "require_testcases": True,
                    "critpath": False,
                    "stable_karma": 3,
                    "date_pushed": None,
                    "requirements": "rpmlint",
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
                        "name": "ralph",
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
                    "alias": "FEDORA-EPEL-2015-0238",
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
