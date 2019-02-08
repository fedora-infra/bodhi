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

from io import BytesIO
from unittest import mock
import datetime
import re

import PIL.Image
import webtest

from bodhi.server import main
from bodhi.tests.server import base


class TestRenderers(base.BaseTestCase):
    def test_renderer_jpeg(self):
        """
        Test that the renderer returns a jpeg. In this case, the CAPTCHA image.
        """
        new_settings = {
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
            'captcha.secret': '2o78T5zF7OERyAtBfC570ZX2TXvfmI3R5mvw6LkG3W0=',
            'captcha.image_width': 300,
            'captcha.image_height': 80,
            'captcha.font_path': '/usr/share/fonts/liberation/LiberationMono-Regular.ttf',
            'captcha.font_size': 36,
            'captcha.font_color': '#000000',
            'captcha.background_color': '#ffffff',
            'captcha.padding': 5,
            'captcha.ttl': 300,
        }
        with mock.patch('bodhi.server.Session.remove'):
            app = webtest.TestApp(main({}, session=self.db, **self.app_settings))

            with mock.patch.dict(app.app.registry.settings, new_settings):
                res = app.get(
                    '/updates/FEDORA-{}-a3bbe1a8f2'.format(datetime.datetime.utcnow().year),
                    status=200, headers=dict(accept='text/html'))
                captcha_url = re.search(r'"http://localhost(/captcha/[^"]*)"', str(res)).groups()[0]
                resp = app.get(captcha_url, status=200)
                self.assertIn('image/jpeg', resp.headers['Content-Type'])
                jpegdata = BytesIO(resp.body)
                img = PIL.Image.open(jpegdata)
                self.assertEqual(img.size, (300, 80))
