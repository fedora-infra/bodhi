# -*- coding: utf-8 -*-
# Copyright © 2016-2018 Red Hat, Inc.
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
"""This test suite contains tests for bodhi.server.captcha."""

import unittest

import mock
import PIL.Image
from pyramid.httpexceptions import HTTPGone, HTTPNotFound
import six

from bodhi.server import captcha
from bodhi.server.config import config


class TestCaptchaImage(unittest.TestCase):
    """Test the captcha_image() function."""

    def test_return_type(self):
        """Assert correct return type."""
        request = mock.MagicMock()
        request.registry.settings = {
            'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA=', 'captcha.ttl': 600,
            'captcha.image_width': 1920, 'captcha.image_height': 1080,
            'captcha.font_path': '/usr/share/fonts/liberation/LiberationMono-Bold.ttf',
            'captcha.font_size': 24, 'captch.font_color': '#012345', 'captcha.padding': 6}
        # We need to put a captcha onto the request.
        cipherkey, url = captcha.generate_captcha(None, request)
        request.matchdict = {'cipherkey': cipherkey}

        image = captcha.captcha_image(request)

        self.assertTrue(isinstance(image, PIL.Image.Image))

    @mock.patch('bodhi.server.captcha.jpeg_generator')
    def test_jpeg_generator_called_correctly(self, jpeg_generator):
        """
        Make sure jpeg_generator() is called correctly.

        We don't have an easy way to make sure the captcha looks right (if we did, it wouldn't be a
        good captcha and also we shouldn't publish it in unit tests), so let's just make sure
        jpeg_generator() is called correctly.
        """
        request = mock.MagicMock()
        request.registry.settings = {
            'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA=', 'captcha.ttl': 600,
            'captcha.image_width': 1920, 'captcha.image_height': 1080,
            'captcha.font_path': '/usr/share/fonts/liberation/LiberationMono-Bold.ttf',
            'captcha.font_size': 24, 'captch.font_color': '#012345', 'captcha.padding': 6}
        # We need to put a captcha onto the request.
        cipherkey, url = captcha.generate_captcha(None, request)
        request.matchdict = {'cipherkey': cipherkey}

        image = captcha.captcha_image(request)

        self.assertEqual(image, jpeg_generator.return_value)
        plainkey = captcha.decrypt(cipherkey, request.registry.settings)
        jpeg_generator.assert_called_once_with(plainkey, request.registry.settings)


class TestDecrypt(unittest.TestCase):
    """Test the decrypt function."""
    @mock.patch.dict(config, {'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA='})
    def test_decrypt_from_encrypt(self):
        """Ensure that decrypt can decrypt what encrypt generated."""
        plaintext = "don't let eve see this!"
        bobs_message = captcha.encrypt(plaintext, config)

        result = captcha.decrypt(bobs_message, config)

        self.assertEqual(result, plaintext)

    @mock.patch.dict(config, {'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA='})
    def test_base64_unsafe(self):
        """Ensure that we raise an HTTPNotFound if the ciphertext is not a base64 safe string"""
        base64_unsafe_message = "$@#his3##d*f"
        with self.assertRaises(HTTPNotFound) as exc:
            captcha.decrypt(base64_unsafe_message, config)

        self.assertEqual(six.text_type(exc.exception), '$@#his3##d*f is garbage')

    @mock.patch.dict(config, {'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA='})
    def test_invalid_token(self):
        """Ensure that we raise a HTTPGone if the token is no longer valid"""
        invalid_token = "!!!!"
        with self.assertRaises(HTTPGone) as exc:
            captcha.decrypt(invalid_token, config)

        self.assertEqual(str(exc.exception), 'captcha token is no longer valid')

    @mock.patch.dict(config, {'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA='})
    def test_text_type_cipherkey(self):
        """Ensure that decrypt can decrypt what encrypt generated, when it is a six.text_type."""
        plaintext = "don't let eve see this!"
        bobs_message = captcha.encrypt(plaintext, config).decode('utf-8')

        result = captcha.decrypt(bobs_message, config)

        self.assertEqual(result, plaintext)


class TestGenerateCaptcha(unittest.TestCase):
    """Test the generate_captcha() function."""

    def test_captcha_can_be_solved(self):
        """Assert that the generated catpcha can be solved."""
        request = mock.MagicMock()
        request.registry.settings = {
            'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA=', 'captcha.ttl': 600}
        request.session = {}

        cipherkey, url = captcha.generate_captcha(None, request)

        self.assertEqual(request.session['captcha'], cipherkey)
        request.route_url.assert_called_once_with('captcha_image', cipherkey=cipherkey)
        self.assertEqual(url, request.route_url.return_value)
        # Let's cheat and find out what the correct value for this cipherkey is and make sure it is
        # accepted by validate().
        plainkey = captcha.decrypt(cipherkey, request.registry.settings)
        value = captcha.math_generator(plainkey, request.registry.settings)[1]
        self.assertTrue(captcha.validate(request, cipherkey, value))


class TestJPEGGenerator(unittest.TestCase):
    """This test class contains tests for the jpeg_generator() function."""
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


class TestValidate(unittest.TestCase):
    """Test the validate() function."""

    def test_match(self):
        r = mock.MagicMock()
        r.registry.settings = {'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA=',
                               'captcha.ttl': 600}
        plaintext = "41 + 1 ="
        cipherkey = captcha.encrypt(plaintext, r.registry.settings)

        self.assertIs(captcha.validate(r, cipherkey, '42'), True)

    def test_no_match(self):
        r = mock.MagicMock()
        r.registry.settings = {'captcha.secret': 'gFqE6rcBXVLssjLjffsQsAa-nlm5Bg06MTKrVT9hsMA=',
                               'captcha.ttl': 600}
        plaintext = "41 + 1 ="
        cipherkey = captcha.encrypt(plaintext, r.registry.settings)

        self.assertIs(captcha.validate(r, cipherkey, '41'), False)
