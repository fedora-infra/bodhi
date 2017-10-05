# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc.
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
"""This module contains tests for bodhi.server.services.errors.py"""
import mock

from bodhi.tests.server import base


class TestHTMLHandlerErrors(base.BaseTestCase):

    @mock.patch('mako.template.Template.render',
                side_effect=[IOError('random error'), mock.DEFAULT])
    def test_template_render_exception(self, template_exception):
        """
        Assert that we log an error if the error template renderer raises an exception
        """
        with self.assertRaises(IOError) as exc:
            self.app.get('/pants', headers={'Accept': 'text/html'}, status=404)

        self.assertEqual(str(exc.exception), 'random error')
