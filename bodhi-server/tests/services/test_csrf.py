# Copyright © 2017-2019 Red Hat, Inc. and others.
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
"""This module contains tests for bodhi.server.services.csrf.py"""
from .. import base


class TestCSRFService(base.BasePyTestCase):

    def test_csrf_html(self):
        """
        Assert that we return just the CSRF token when requesting HTML
        """
        res = self.app.get('/csrf', headers={'Accept': 'text/html'}, status=200)

        assert res.body.decode('utf-8') == self.get_csrf_token()

    def test_csrf_json(self):
        """
        Assert that we return the CSRF token in JSON format when requesting JSON
        """
        res = self.app.get('/csrf', headers={'Accept': 'application/json'}, status=200)

        assert res.body.decode('utf-8') == '{"csrf_token": "%s"}' % self.get_csrf_token()
