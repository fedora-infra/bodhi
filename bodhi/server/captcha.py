# -*- coding: utf-8 -*-
# Copyright © 2014-2018 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
#
# Authors:  Ralph Bean <rbean@redhat.com>
"""Define utilities and a view pertaining to captcha images for unauthenticated users."""

from __future__ import division
import base64
import math
import random
import binascii

from PIL import Image, ImageDraw, ImageFont
from pyramid.httpexceptions import HTTPGone, HTTPNotFound
from pyramid.view import view_config
import cryptography.fernet
import six


def math_generator(plainkey, settings):
    """
    Given a plainkey, return its expected value.

    Args:
        plainkey (basestring or None): The key to encrypt as ciphertext. If None, a random key is
            generated.
        settings (bodhi.server.config.BodhiConfig): Bodhi's settings, unsued.
    Returns:
        tuple: A 2-tuple is returned. The first element is the plainkey, and the second is its
            encrypted value.
    Raises:
        ValueError: If the plainkey is not valid.
    """
    if not plainkey:
        x = random.randint(1, 100)
        y = random.randint(1, 100)
        plainkey = "%i + %i =" % (x, y)

    tokens = plainkey.split()
    if not len(tokens) == 4:
        raise ValueError("%s is an invalid plainkey" % plainkey)

    if tokens[1] != '+' or tokens[3] != '=':
        raise ValueError("%s is an invalid plainkey" % plainkey)

    x, y = int(tokens[0]), int(tokens[2])

    value = six.text_type(x + y)
    return plainkey, value


def jpeg_generator(plainkey, settings):
    """
    Generate an image with plainkey written in it.

    Args:
        plainkey (basestring): The text to include in the generated image.
        settings (bodhi.server.config.BodhiConfig): Bodhi's settings.
    Returns:
        PIL.Image.Image: An image containing the given text.
    """
    image_size = image_width, image_height = (
        settings.get('captcha.image_width'),
        settings.get('captcha.image_height'),
    )
    font_path = settings.get('captcha.font_path')
    font_size = settings.get('captcha.font_size')
    font_color = settings.get('captcha.font_color')
    background_color = settings.get('captcha.background_color')
    padding = settings.get('captcha.padding')

    img = Image.new('RGB', image_size, color=background_color)

    font = ImageFont.truetype(font_path, font_size)
    width, height = font.getsize(plainkey)

    draw = ImageDraw.Draw(img)
    position = (
        random.randint(padding, (image_width - width - padding)),
        random.randint(padding, (image_height - height - padding)))
    draw.text(position, plainkey, font=font, fill=font_color)

    # Make it crazy!
    img = warp_image(img)

    return img


def warp_image(image):
    """
    Apply some random bending operations to the given image.

    This function attempts to make it harder for bots to read the text inside the image, while
    allowing humans to read it.

    Args:
        image (PIL.Image.Image): The image to warp.
    Returns:
        PIL.Image.Image: A warped transformation of the given image.
    """
    r = 10  # individually warp a bunch of 10x10 tiles.
    mesh_x = (image.size[0] // r) + 2
    mesh_y = (image.size[1] // r) + 2

    # Set up some random values we'll use over and over...
    amplitude = random.uniform(6, 10)
    period = random.uniform(0.65, 0.74)
    offset = (
        random.uniform(0, math.pi * 2 / period),
        random.uniform(0, math.pi * 2 / period),
    )

    def _sine(x, y, a=amplitude, p=period, o=offset):
        """Given a single point, warp it."""
        return (
            math.sin((y + o[0]) * p) * a + x,
            math.sin((x + o[1]) * p) * a + y,
        )

    def _clamp(x, y):
        """Don't warp things outside the bounds of the image."""
        return (
            max(0, min(image.size[0] - 1, x)),
            max(0, min(image.size[1] - 1, y)),
        )

    # Build a map of the corners of our r by r tiles, warping each one.
    warp = [
        [
            _clamp(*_sine(i * r, j * r))
            for j in range(mesh_y)
        ] for i in range(mesh_x)
    ]

    def _destination_rectangle(i, j):
        """Return a happy tile from the original space."""
        return (i * r, j * r, (i + 1) * r, (j + 1) * r)

    def _source_quadrilateral(i, j):
        """
        Return the set of warped corners for a given tile.

        Specified counter-clockwise as a tuple.
        """
        return (
            warp[i][j][0], warp[i][j][1],
            warp[i][j + 1][0], warp[i][j + 1][1],
            warp[i + 1][j + 1][0], warp[i + 1][j + 1][1],
            warp[i + 1][j][0], warp[i + 1][j][1],
        )

    # Finally, prepare our list of sources->destinations for PIL.
    mesh = [
        (
            _destination_rectangle(i, j),
            _source_quadrilateral(i, j),
        )
        for j in range(mesh_y - 1)
        for i in range(mesh_x - 1)
    ]
    # And do it.
    return image.transform(image.size, Image.MESH, mesh, Image.BILINEAR)


def validate(request, cipherkey, value):
    """
    Return whether the value matches the expected value, based on the cipherkey.

    Args:
        request (pyramid.util.Request): The current web request.
        cipherkey (basestring): The encrypted Fernet key.
        value (basestring): The value to be validated.
    Returns:
        bool: True if value matches the expected value based on the cipherkey, False otherwise.
            False is also returned if the cipherkey is not found to be a valid Fernet token.
    """
    settings = request.registry.settings

    plainkey = decrypt(cipherkey, settings)

    _, expected_value = math_generator(plainkey=plainkey, settings=settings)
    return value == expected_value


def generate_captcha(context, request):
    """
    Generate a key and a URL to a captcha image that matches the key.

    Args:
        context (mako.runtime.Context): Unused.
        request (pyramid.util.Request): The current web request.
    Returns:
        tuple: A 2-tuple of strings. The first is the ciphertext key for a captcha, and the second
            is a URL to the captcha image that matches that key.
    """
    settings = request.registry.settings
    plainkey, value = math_generator(plainkey=None, settings=settings)
    cipherkey = encrypt(plainkey, settings)
    url = request.route_url('captcha_image', cipherkey=cipherkey)
    request.session['captcha'] = cipherkey  # Remember this to stop replay.
    return cipherkey, url


def encrypt(plaintext, settings):
    """
    Calculate and return the ciphertext key from the given plaintext key.

    Args:
        plaintext (basestring): A key you wish you encrypt.
        settings (bodhi.server.config.BodhiConfig): Bodhi's settings.
    Returns:
        str: The ciphertext version of the given captcha key.
    """
    secret = settings['captcha.secret']
    engine = cryptography.fernet.Fernet(secret)
    ciphertext = engine.encrypt(plaintext.encode('utf-8'))
    ciphertext = base64.urlsafe_b64encode(ciphertext)
    return ciphertext


def decrypt(ciphertext, settings):
    """
    Calculate and return the plaintext key from the given ciphertext.

    Args:
        ciphertext (str): The encrypted secret for a captcha image.
        settings (bodhi.server.config.BodhiConfig): Bodhi's settings.
    Returns:
        unicode: The plaintext secret for a captcha image.
    Raises:
        pyramid.httpexceptions.HTTPNotFound: If the ciphertext can not be decoded as base64.
        pyramid.httpexceptions.HTTPGone: If the captcha token has expired.
    """
    ttl = settings['captcha.ttl']
    secret = settings['captcha.secret']
    engine = cryptography.fernet.Fernet(secret)

    if isinstance(ciphertext, six.text_type):
        ciphertext = ciphertext.encode('utf-8')

    try:
        ciphertext = base64.urlsafe_b64decode(ciphertext)
    except (TypeError, binascii.Error):
        raise HTTPNotFound("%s is garbage" % ciphertext.decode('utf-8'))

    try:
        plaintext = engine.decrypt(ciphertext, ttl=ttl)
    except cryptography.fernet.InvalidToken:
        raise HTTPGone('captcha token is no longer valid')

    return plaintext.decode('utf-8')


@view_config(route_name='captcha_image', renderer='jpeg')
def captcha_image(request):
    """
    Generate and return a captcha image.

    Args:
        request (pyramid.util.Request): The current web request.
    Returns:
        PIL.Image.Image: The generated captcha image.
    """
    cipherkey = request.matchdict['cipherkey']
    plainkey = decrypt(cipherkey, request.registry.settings)
    image = jpeg_generator(plainkey, request.registry.settings)
    return image
