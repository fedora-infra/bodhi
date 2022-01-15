# Copyright © 2020 Red Hat, Inc. and others.
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
"""This module contains classes for testsing the submodules of bodhi.server.tasks."""

from unittest import mock

from ..base import BasePyTestCase


class BaseTaskTestCase(BasePyTestCase):
    """
    Mock the transactional_session_maker used in tasks.

    This prevents it from closing and removing the session.
    """

    def setup_method(self, method):
        """Patch transactional_session_maker."""
        super().setup_method(method)
        self._tsm_patcher = mock.patch('bodhi.server.util.transactional_session_maker._end_session')
        self._tsm_patcher.start()

    def teardown_method(self, method):
        """Unpatch transactional_session_maker."""
        self._tsm_patcher.stop()
        super().teardown_method(method)
