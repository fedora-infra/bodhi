# Copyright © 2019 Red Hat, Inc.
#
# This file is part of Bodhi.
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
"""Test bodhi.server.logging."""

import logging
from unittest import mock

from bodhi.server import logging as bodhi_logging


test_log = logging.Logger(__name__)


class TestSetup:
    """Test the setup() function."""

    @mock.patch(
        'bodhi.server.logging.config.config',
        {'pyramid.includes': 'some_plugin\npyramid_sawing\nsome_other_plugin',
         'pyramid_sawing.file': '/some/file'})
    @mock.patch('bodhi.server.logging.logging.config.dictConfig')
    def test_with_sawing(self, dictConfig):
        """Test for when the user is using pyramid_sawing."""
        with mock.patch('builtins.open',
                        mock.mock_open(read_data='some: data')) as mock_open:
            bodhi_logging.setup()

        mock_open.assert_called_once_with('/some/file')
        dictConfig.assert_called_once_with({'some': 'data'})

    @mock.patch.dict('bodhi.server.logging.config.config',
                     {'pyramid.includes': 'some_plugin\nsome_other_plugin'})
    @mock.patch('bodhi.server.logging.config.get_configfile',
                mock.MagicMock(return_value='/test/file'))
    @mock.patch('bodhi.server.logging.paster.setup_logging')
    def test_without_sawing(self, setup_logging):
        """Test for when the user is not using pyramid_sawing."""
        bodhi_logging.setup()

        setup_logging.assert_called_once_with('/test/file')


class TestRateLimiter:
    """
    Test the RateLimiter class.

    These tests were stolen from
    https://github.com/fedora-infra/fedmsg-migration-tools/blob/0cafc8f5/fedmsg_migration_tools/tests/test_filters.py
    """

    def test_filter_new_record(self):
        """Assert a new record is not limited."""
        record = test_log.makeRecord(
            "test_name", logging.INFO, "/my/file.py", 3, "beep boop", tuple(), None)
        rate_filter = bodhi_logging.RateLimiter()

        assert rate_filter.filter(record)

    def test_filter_false(self):
        """Assert if the filename:lineno entry exists and is new, it's filtered out."""
        record = test_log.makeRecord(
            "test_name", logging.INFO, "/my/file.py", 3, "beep boop", tuple(), None)
        rate_filter = bodhi_logging.RateLimiter(rate=2)
        rate_filter._sent["/my/file.py:3"] = record.created - 1

        assert not rate_filter.filter(record)

    def test_rate_is_used(self):
        """Assert custom rates are respected."""
        record = test_log.makeRecord(
            "test_name", logging.INFO, "/my/file.py", 3, "beep boop", tuple(), None)
        rate_filter = bodhi_logging.RateLimiter(rate=2)
        rate_filter._sent["/my/file.py:3"] = record.created - 2

        assert rate_filter.filter(record)

    def test_rate_limited(self):
        """Assert the first call is allowed and the subsequent one is not."""
        record = test_log.makeRecord(
            "test_name", logging.INFO, "/my/file.py", 3, "beep boop", tuple(), None)
        rate_filter = bodhi_logging.RateLimiter(rate=60)

        assert rate_filter.filter(record)
        assert not rate_filter.filter(record)

    def test_different_lines(self):
        """Assert rate limiting is line-dependent."""
        record1 = test_log.makeRecord(
            "test_name", logging.INFO, "/my/file.py", 3, "beep boop", tuple(), None)
        record2 = test_log.makeRecord(
            "test_name", logging.INFO, "/my/file.py", 4, "beep boop", tuple(), None)
        rate_filter = bodhi_logging.RateLimiter()

        assert rate_filter.filter(record1)
        assert rate_filter.filter(record2)
