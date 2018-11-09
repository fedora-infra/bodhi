# Copyright © 2018 Red Hat, Inc.
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

from tests.utils import read_file


def test_get_root(bodhi_container):
    # GET on /
    # this is standard `requests.Response`
    http_response = bodhi_container.http_request(path="/", port=8080)
    try:
        assert http_response.ok
        assert "Fedora Update System" in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise
