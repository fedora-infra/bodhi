"""Some utilities for bodhi-server's unit tests."""

from unittest import TestCase

_dummy = TestCase()
assert_multiline_equal = _dummy.assertMultiLineEqual
