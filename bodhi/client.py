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

from fedora.client import OpenIdBaseClient

BASE_URL = 'http://127.0.0.1:6543'


class BodhiClient(OpenIdBaseClient):

    def __init__(self, base_url=BASE_URL, **kwargs):
        super(BodhiClient, self).__init__(base_url, **kwargs)

    def new(self, **kwargs):
        return self.send_request('/updates/', verb='POST', auth=True,
                                 data=kwargs)

    def query(self, **kwargs):
        return self.send_request('/updates/', verb='GET', params=kwargs)
