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

import base64
import cryptography.fernet
import random
import six

from PIL import Image, ImageDraw, ImageFont

from pyramid.httpexceptions import HTTPGone, HTTPNotFound
from pyramid.view import view_config


def math_generator(plainkey, settings):
    """ Given a plainkey, return its expected value.
    If plainkey is None, return a random one.
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
    image_size = image_width, image_height = (
        int(settings.get('captcha.image_width', 300)),
        int(settings.get('captcha.image_height', 80)),
    )
    default_font = '/usr/share/fonts/liberation/LiberationMono-Regular.ttf'
    font_path = settings.get('captcha.font_path', default_font)
    font_size = int(settings.get('captcha.font_size', 36))
    font_color = settings.get('captcha.font_color', '#000000')
    background_color = settings.get('captcha.background_color', '#ffffff')
    padding = int(settings.get('captcha.padding', 5))

    img = Image.new('RGB', image_size)

    img.paste(background_color)

    font = ImageFont.truetype(font_path, font_size)
    width, height = font.getsize(plainkey)

    draw = ImageDraw.Draw(img)
    position = (
        random.randint(padding, (image_width - width - padding)),
        random.randint(padding, (image_height - height - padding)))
    draw.text(position, plainkey, font=font, fill=font_color)

    return img


def validate(request, cipherkey, value):
    settings = request.registry.settings

    try:
        plainkey = decrypt(cipherkey, settings)
    except cryptography.fernet.InvalidToken:
        return False

    _, expected_value = math_generator(plainkey=plainkey, settings=settings)
    return value == expected_value


def generate_captcha(context, request):
    settings = request.registry.settings
    plainkey, value = math_generator(plainkey=None, settings=settings)
    cipherkey = encrypt(plainkey, settings)
    url = request.route_url('captcha_image', cipherkey=cipherkey)
    return cipherkey, url


def encrypt(plaintext, settings):
    secret = settings['captcha.secret']
    engine = cryptography.fernet.Fernet(secret)
    ciphertext = engine.encrypt(plaintext.encode('utf-8'))
    ciphertext = base64.urlsafe_b64encode(ciphertext)
    return ciphertext


def decrypt(ciphertext, settings):
    ttl = int(settings['captcha.ttl'])
    secret = settings['captcha.secret']
    engine = cryptography.fernet.Fernet(secret)

    if isinstance(ciphertext, six.text_type):
        ciphertext = ciphertext.encode('utf-8')

    try:
        ciphertext = base64.urlsafe_b64decode(ciphertext)
    except TypeError:
        raise HTTPNotFound("%s is garbage" % ciphertext)

    try:
        plaintext = engine.decrypt(ciphertext, ttl=ttl)
    except cryptography.fernet.InvalidToken:
        raise HTTPGone('captcha token is no longer valid')

    return plaintext.decode('utf-8')


@view_config(route_name='captcha_image', renderer='jpeg')
def captcha_image(request):
    cipherkey = request.matchdict['cipherkey']
    plainkey = decrypt(cipherkey, request.registry.settings)
    image = jpeg_generator(plainkey, request.registry.settings)
    return image
