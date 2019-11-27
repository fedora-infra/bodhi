# Copyright © 2018, 2019 Red Hat, Inc.
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
"""Test the bodhi package."""

from unittest import TestCase

import _pytest.logging


__all__ = ['assert_multiline_equal']


if not hasattr(_pytest.logging.LogCaptureFixture, 'messages'):
    # Monkey patch old versions of _pytest.logging.LogCaptureFixture
    class MonkeyLogCaptureFixture(_pytest.logging.LogCaptureFixture):
        """Adds 'messages' property to LogCaptureFixture."""

        @property
        def messages(self):
            """Return a list of format-interpolated log messages."""
            return [r.getMessage() for r in self.records]

    _pytest.logging.LogCaptureFixture = MonkeyLogCaptureFixture


_dummy = TestCase()
assert_multiline_equal = _dummy.assertMultiLineEqual
