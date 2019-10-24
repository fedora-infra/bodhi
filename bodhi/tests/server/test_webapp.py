# Copyright © 2018-2019 Red Hat, Inc.
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
"""Tests for bodhi.server.webapp."""

from unittest import mock

from bodhi.server import webapp


class TestCompleteDatabaseSession:
    """Test the _complete_database_session() function."""

    def test_cleanup_exception(self):
        """Test for rollback() when there is an Exception."""
        request = mock.Mock()
        request.exception = IOError('The Internet ran out of cats.')

        with mock.patch('bodhi.server.Session') as Session_mock:
            webapp._complete_database_session(request)

        # Since there was an Exception, the session should have been rolled back and closed.
        assert Session_mock.return_value.rollback.mock_calls == [mock.call()]
        assert Session_mock.return_value.commit.mock_calls == []
        assert Session_mock.return_value.close.mock_calls == [mock.call()]
        assert Session_mock.remove.mock_calls == [mock.call()]

    def test_cleanup_no_exception(self):
        """Test cleanup() when there is not an Exception."""
        request = mock.Mock()
        request.exception = None

        with mock.patch('bodhi.server.Session') as Session:
            webapp._complete_database_session(request)

        # Since there was no Exception, the session should have been committed and closed.
        assert Session.return_value.rollback.mock_calls == []
        assert Session.return_value.commit.mock_calls == [mock.call()]
        assert Session.return_value.close.mock_calls == [mock.call()]
        assert Session.remove.mock_calls == [mock.call()]


class TestPrepareRequest:
    """Test the _prepare_request() function."""

    def test_adds_db_cleanup_callback(self):
        event = mock.MagicMock()

        webapp._prepare_request(event)

        event.request.add_finished_callback.assert_called_once_with(
            webapp._complete_database_session)
