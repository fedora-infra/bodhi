# -*- coding: utf-8 -*-

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
"""This test suite contains tests for bodhi.server.captcha."""

import unittest

import mock

from bodhi.server import captcha


class TestMathGenerator(unittest.TestCase):
    """This test class contains tests for the math_generator() function.
    
    Every test here passes None as the second settings argument to math_generator(), as that
    parameter is not used.
    """
    def test_fourth_token_not_equals(self):
        """
        Assert that ValueError is raised when the last token is not "=".
        """
        self.assertRaises(ValueError, captcha.math_generator, '42 + 6790 ', None)

    def test_plainkey_None_deterministic(self):
        """
        Assert correct behavior when plainkey is passed as None using a mocked random so we get a
        deterministic response.
        """
        with mock.patch('bodhi.server.captcha.random.randint', side_effect=[1, 2]):
            puzzle, value = captcha.math_generator(None, None)

        self.assertEqual(puzzle, '1 + 2 =')
        self.assertEqual(value, '3')

    def test_plainkey_None_nondeterministic(self):
        """
        Assert correct behavior when plainkey is passed as None without mocking random. For this
        test, we will assert that the math summation matches the expected value.
        """
        puzzle, value = captcha.math_generator(None, None)

        puzzle = puzzle.split()
        self.assertEqual(int(puzzle[0]) + int(puzzle[2]), int(value))
        self.assertEqual(puzzle[1], '+')
        self.assertEqual(puzzle[3], '=')

    def test_second_token_not_plus(self):
        """
        Assert that ValueError is raised when the second token is not "+".
        """
        self.assertRaises(ValueError, captcha.math_generator, '42 * 6790 =', None)

    def test_tokens_len_not_4(self):
        """
        Assert that ValueError is raised if the length of the split tokens is not four.
        """
        self.assertRaises(ValueError, captcha.math_generator, '42 + 6790 + 2 =', None)

    def test_with_plainkey(self):
        """
        Assert correct return value when passing a valid plainkey to the function.
        """
        puzzle, value = captcha.math_generator('42 + 7 =', None)

        self.assertEqual(puzzle, '42 + 7 =')
        self.assertEqual(value, '49')
