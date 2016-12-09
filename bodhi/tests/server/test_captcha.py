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
import PIL.Image

from bodhi.server import captcha


class TestJPEGGenerator(unittest.TestCase):
    """This test class contains tests for the jpeg_generator() function."""
    def test_with_defaults(self):
        """Test the jpeg_generator with default settings."""
        img = captcha.jpeg_generator('42 + 7', {})

        img.verify()
        self.assertTrue(isinstance(img, PIL.Image.Image))
        # Ensure the image is the default size
        self.assertEqual(img.size, (300, 80))
        self.assertEqual(img.mode, 'RGB')

    @mock.patch('bodhi.server.captcha.ImageDraw.Draw')
    @mock.patch('bodhi.server.captcha.ImageFont.truetype')
    @mock.patch('bodhi.server.captcha.random.randint')
    def test_with_heavy_mocking(self, randint, truetype, Draw):
        """
        Test the generator with heavy mocking so we can make sure all the right calls were made.
        """
        randint.side_effect = [52, 78]
        truetype.return_value.getsize = mock.MagicMock(return_value=(100, 80))

        settings = {
            'captcha.image_width': 1920, 'captcha.image_height': 1080,
            'captcha.font_path': '/path/to/cool/font',
            'captcha.font_size': 24, 'captcha.font_color': '#012345', 'captcha.padding': 6}

        img = captcha.jpeg_generator('42 + 7', settings)

        truetype.assert_called_once_with('/path/to/cool/font', 24)
        truetype.return_value.getsize.assert_called_once_with('42 + 7')
        Draw.assert_called_once_with(img)
        Draw.return_value.text.assert_called_once_with((52, 78), '42 + 7',
                                                       font=truetype.return_value, fill='#012345')
        img.verify()
        self.assertTrue(isinstance(img, PIL.Image.Image))
        # Ensure the image is the default size
        self.assertEqual(img.size, (1920, 1080))
        self.assertEqual(img.mode, 'RGB')

    def test_with_specified_parameters(self):
        """Test the generator with specified dimensions."""
        settings = {
            'captcha.image_width': 1920, 'captcha.image_height': 1080,
            'captcha.font_path': '/usr/share/fonts/liberation/LiberationMono-Bold.ttf',
            'captcha.font_size': 24, 'captch.font_color': '#012345', 'captcha.padding': 6}

        img = captcha.jpeg_generator('42 + 7', settings)

        img.verify()
        self.assertTrue(isinstance(img, PIL.Image.Image))
        # Ensure the image is the default size
        self.assertEqual(img.size, (1920, 1080))
        self.assertEqual(img.mode, 'RGB')


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
