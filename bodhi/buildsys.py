# $Id: $
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import koji

from os.path import join, expanduser
from turbogears import config

# Our singleton koji ClientSession
session = None

def get_session():
    """
    Get a singleton Koji ClientSession instance
    """
    global session
    if not session:
        session = login()
    return session

def login(client=join(expanduser('~'), '.koji/client.crt'),
          clientca=join(expanduser('~'), '.koji/clientca.crt'),
          serverca=join(expanduser('~'), '.koji/serverca.crt')):
    """
    Login to Koji and return the session
    """
    koji_session = koji.ClientSession(config.get('koji_hub'), {})
    koji_session.ssl_login(client, clientca, serverca)
    return koji_session
