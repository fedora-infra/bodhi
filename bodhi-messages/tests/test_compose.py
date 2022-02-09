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
"""Unit tests for the compose message schemas."""


from bodhi.messages.schemas.compose import (
    ComposeComposingV1,
    ComposeStartV1,
    ComposeCompleteV1,
    ComposeSyncWaitV1,
    ComposeSyncDoneV1,
    RepoDoneV1,
)
from .utils import check_message


class TestComposeMessage:
    """A set of unit tests for classes in :py:mod:`bodhi_messages.schemas.compose`"""

    def test_composing_v1(self):
        expected = {
            "topic": "bodhi.compose.composing",
            "summary": "bodhi composer started composing test_repo",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "usernames": ['mohanboddu'],
            "packages": [],
            'repo': 'test_repo',
            'agent': 'mohanboddu'
        }
        msg = ComposeComposingV1(
            body={
                'agent': 'mohanboddu',
                'repo': 'test_repo',
                'updates': ['monitorix-3.11.0-1.el6'],
            }
        )
        check_message(msg, expected)

    def test_start_v1(self):
        expected = {
            "topic": "bodhi.compose.start",
            "summary": "bodhi composer started a push",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "usernames": ['mohanboddu'],
            "packages": [],
            'agent': 'mohanboddu'
        }
        msg = ComposeStartV1(body={'agent': 'mohanboddu'})
        check_message(msg, expected)

    def test_complete_v1_failed(self):
        """Test the ComposeCompleteV1 Message with a failed compose."""
        expected = {
            "topic": "bodhi.compose.complete",
            "summary": "bodhi composer failed to compose test_repo",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "usernames": ['mohanboddu'],
            "packages": [],
            'agent': 'mohanboddu',
            'repo': 'test_repo',
            'success': False,
            'ctype': 'container',
        }
        msg = ComposeCompleteV1(
            body={
                'agent': 'mohanboddu',
                'success': False,
                'repo': 'test_repo',
                'ctype': 'container',
            }
        )
        check_message(msg, expected)

    def test_complete_v1_success(self):
        """Test the ComposeCompleteV1 Message with a successful compose."""
        expected = {
            "topic": "bodhi.compose.complete",
            "summary": "bodhi composer successfully composed test_repo",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "usernames": ['mohanboddu'],
            "packages": [],
            'agent': 'mohanboddu',
            'repo': 'test_repo',
            'success': True,
            'ctype': 'container',
        }
        msg = ComposeCompleteV1(
            body={
                'agent': 'mohanboddu',
                'success': True,
                'repo': 'test_repo',
                'ctype': 'container',
            }
        )
        check_message(msg, expected)

    def test_repo_done_v1(self):
        expected = {
            "topic": "bodhi.repo.done",
            "summary": "bodhi composer is finished building test_repo",
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "usernames": ['mohanboddu'],
            "packages": [],
            'agent': 'mohanboddu',
            'repo': 'test_repo'
        }
        msg = RepoDoneV1(
            body={'agent': 'mohanboddu', 'repo': 'test_repo', 'path': '/some/path'}
        )
        check_message(msg, expected)

    def test_sync_wait_v1(self):
        expected = {
            "topic": "bodhi.compose.sync.wait",
            "summary": (
                "bodhi composer is waiting for test_repo "
                "to hit the master mirror"
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "usernames": ['mohanboddu'],
            "packages": [],
            'agent': 'mohanboddu',
            'repo': 'test_repo'
        }
        msg = ComposeSyncWaitV1(
            body={'agent': 'mohanboddu', 'repo': 'test_repo'}
        )
        check_message(msg, expected)

    def test_sync_done_v1(self):
        expected = {
            "topic": "bodhi.compose.sync.done",
            "summary": (
                "bodhi composer finished waiting for test_repo "
                "to hit the master mirror"
            ),
            "app_icon": "https://apps.fedoraproject.org/img/icons/bodhi.png",
            "url": None,
            "usernames": ['mohanboddu'],
            "packages": [],
            'agent': 'mohanboddu',
            'repo': 'test_repo'
        }
        msg = ComposeSyncDoneV1(
            body={'agent': 'mohanboddu', 'repo': 'test_repo'}
        )
        check_message(msg, expected)
