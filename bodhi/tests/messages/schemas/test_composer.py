# Copyright (C) 2018-2019  Red Hat, Inc.
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
"""Unit tests for the composer message schemas."""

import unittest

from bodhi.messages.schemas.composer import ComposeV1, ComposerStartV1
from bodhi.tests.messages.utils import check_message


class ComposerMessageTests(unittest.TestCase):
    """A set of unit tests for classes in :py:mod:`bodhi_messages.schemas.composer`"""

    def test_start_v1(self):
        expected = {
            "topic": "bodhi.composer.start",
            "summary": "mohanboddu requested a compose of 2 repositories",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "agent_avatar": (
                "https://seccdn.libravatar.org/avatar/"
                "20652954adacfd9f6e26536bbcf3b5fbc850dc61f8a2e67c5bfbc6e345032976"
                "?s=64&d=retro"
            ),
            "usernames": ["mohanboddu"],
            "packages": [],
            'resume': False,
            'agent': 'mohanboddu',
            'composes': [ComposeV1(21, 'stable', 'rpm', True), ComposeV1(23, 'stable', 'rpm', True)]
        }
        msg = ComposerStartV1(
            body={
                "resume": False,
                "api_version": 2,
                "agent": "mohanboddu",
                "composes": [
                    {"security": True,
                     "release_id": 21,
                     "request": "stable",
                     "content_type": "rpm"},
                    {"security": True,
                     "release_id": 23,
                     "request": "stable",
                     "content_type": "rpm"}]})
        check_message(msg, expected)
