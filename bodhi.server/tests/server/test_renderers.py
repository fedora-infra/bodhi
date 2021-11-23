# Copyright © 2019 Red Hat, Inc.
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
"""Test bodhi.server.renderers."""

import pytest
from pyramid.exceptions import HTTPBadRequest
from pyramid.testing import DummyRequest

from bodhi.server import renderers


class TestRSS:
    """Test the rss() function."""

    def test_invalid_no_request(self):
        """HTTPBadRequest should be raised if data can't be rendered and there's no request."""
        with pytest.raises(HTTPBadRequest) as exc:
            renderers.rss(None)({}, {})
        assert str(exc.value) == 'Invalid RSS feed request'

    def test_invalid_request(self):
        """HTTPBadRequest should be raised if the data isn't a type we can render."""
        request = DummyRequest()

        text = renderers.rss(None)({}, {'request': request})

        assert text == 'Invalid RSS feed request'
        assert request.response.status_code == 400
