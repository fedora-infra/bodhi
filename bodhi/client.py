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

import logging
import warnings

from fedora.client import OpenIdBaseClient
import fedora.client.openidproxyclient

__version__ = '2.0.0'
log = logging.getLogger(__name__)

BASE_URL = 'https://admin.fedoraproject.org/updates/'
STG_BASE_URL = 'https://admin.stg.fedoraproject.org/updates/'
STG_OPENID_API = 'https://id.stg.fedoraproject.org/api/v1/'


class BodhiClient(OpenIdBaseClient):

    def __init__(self, base_url=BASE_URL, username=None, password=None, staging=False, **kwargs):
        if staging:
            log.info('Using bodhi2 STAGING environment')
            base_url = 'https://admin.stg.fedoraproject.org/updates/'
            fedora.client.openidproxyclient.FEDORA_OPENID_API = 'https://id.stg.fedoraproject.org/api/v1/'
        super(BodhiClient, self).__init__(base_url, login_url=base_url+ 'login', debug=True, **kwargs)

        if username and password:
            self.login(username, password)

    def new(self, **kwargs):
        return self.send_request('updates/', verb='POST', auth=True,
                                 data=kwargs)

    def query(self, **kwargs):
        return self.send_request('updates', verb='GET', params=kwargs)

    def csrf(self, **kwargs):
        return self.send_request('csrf', verb='GET', params=kwargs).json()['csrf_token']

    def parse_file(self, input_file):
        """ Parse an update template file.

        :arg input_file: The filename of the update template.

        Returns an array of dictionaries of parsed update values which
        can be directly passed to the ``save`` method.

        """
        from ConfigParser import SafeConfigParser
        import os

        if not os.path.exists(input_file):
            raise ValueError("No such file or directory: %s" % input_file)

        config = SafeConfigParser()
        read = config.read(input_file)

        if len(read) != 1 or read[0] != input_file:
            raise ValueError("Invalid input file: %s" % input_file)

        updates = []

        for section in config.sections():
            update = {
                'builds': section, 'bugs': config.get(section, 'bugs'),
                'close_bugs': config.getboolean(section, 'close_bugs'),
                'type': config.get(section, 'type'),
                'request': config.get(section, 'request'),
                'severity': config.get(section, 'severity'),
                'notes': config.get(section, 'notes'),
                'autokarma': config.get(section, 'autokarma'),
                'stable_karma': config.get(section, 'stable_karma'),
                'unstable_karma': config.get(section, 'unstable_karma'),
                'suggest': config.get(section, 'suggest'),
                }

            updates.append(update)

        return updates
