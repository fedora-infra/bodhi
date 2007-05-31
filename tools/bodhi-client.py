#!/usr/bin/env python
# $Id: $
#
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

"""
TODO: ability to fetch srpms for any given nvr?
submit and update
request a push/move/unpush
+1/-1 or comment on test updates
"""

import sys
import xmlrpclib

from optparse import OptionParser

__version__ = '$Revision: $'[11:-2]
__description__ = 'Command line tool for interacting with Bodhi'

BODHI_RPC = 'http://admin.fedoraproject.org/updates/rpc'

class BodhiClient:
    """
    A command-line client to interact with a Bodhi instance.
    """

    def __init__(self):
        self.rpc = xmlrpclib.Server(BODHI_RPC)

    def show(self, package):
        print self.rpc.show(package)

def usage():
    print """\
Usage: %s <command>

Commands:
    - show <package> : Show details of a given package or update
""" % sys.argv[0]

if __name__ == '__main__':
    bodhi = BodhiClient()
    try:
        if sys.argv[1] == 'show':
            bodhi.show(sys.argv[2])
    except IndexError:
        usage()
        sys.exit(1)
