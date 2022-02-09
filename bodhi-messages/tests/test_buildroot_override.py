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
"""Unit tests for the buildroot_override message schemas."""

from bodhi.messages.schemas import base
from bodhi.messages.schemas.buildroot_override import (BuildrootOverrideTagV1,
                                                       BuildrootOverrideUntagV1)
from .utils import check_message


class TestBuildrootOverrideMessage:
    """A set of unit tests for classes in :py:mod:`bodhi_messages.schemas.buildroot_override`"""

    def test_tag_v1(self):
        expected = {
            "topic": "bodhi.buildroot_override.tag",
            "summary": "lmacken submitted a buildroot override for libxcrypt-4.4.4-2.fc28",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/overrides/libxcrypt-4.4.4-2.fc28",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "203f6cb95b44b5d38aa21425b066dd522d3e19d8919cf4b339f29e0ea7f03e9b"
                "?s=64&d=retro"
            ),
            "usernames": ["lmacken"],
            "packages": ["libxcrypt"],
            'build': base.BuildV1('libxcrypt-4.4.4-2.fc28'),
            'submitter': base.UserV1('lmacken'),
            'agent': 'lmacken'
        }
        msg = BuildrootOverrideTagV1(
            body={
                "override": {
                    "nvr": "libxcrypt-4.4.4-2.fc28",
                    "submitter": {'name': 'lmacken'},
                }
            }
        )
        check_message(msg, expected)

    def test_untag_v1(self):
        expected = {
            "topic": "bodhi.buildroot_override.untag",
            "summary": "lmacken expired a buildroot override for libxcrypt-4.4.4-2.fc28",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": "https://bodhi.fedoraproject.org/overrides/libxcrypt-4.4.4-2.fc28",
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "203f6cb95b44b5d38aa21425b066dd522d3e19d8919cf4b339f29e0ea7f03e9b"
                "?s=64&d=retro"
            ),
            "usernames": ["lmacken"],
            "packages": ["libxcrypt"],
            'build': base.BuildV1('libxcrypt-4.4.4-2.fc28'),
            'submitter': base.UserV1('lmacken'),
            'agent': 'lmacken'
        }
        msg = BuildrootOverrideUntagV1(
            body={
                "override": {
                    "nvr": "libxcrypt-4.4.4-2.fc28",
                    "submitter": {"name": "lmacken"},
                }
            }
        )
        check_message(msg, expected)
