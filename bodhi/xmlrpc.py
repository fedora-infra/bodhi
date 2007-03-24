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

import logging
import cherrypy

from model import PackageUpdate, Package
from sqlobject import SQLObjectNotFound
from turbogears import expose
from turbogears.controllers import Controller

log = logging.getLogger(__name__)

class XmlRpcController(Controller):
    """
    Bodhi's XML-RPC interface.
    """
    def __init__(self):
        cherrypy.config.update({'xmlrpc_filter.on' : True})

    @expose()
    def show(self, package=None):
        """
        Display information for a given package/update
        """
        if package:
            # check for existing update as pkg-ver-rel
            log.debug("Checking for existing update as pkg-ver-rel")
            try:
                update = PackageUpdate.byNvr(package)
                return str(update)
            except SQLObjectNotFound:
                # check for package
                log.debug("Checking for package %s" % package)
                try:
                    pkg = Package.byName(package)
                    return str(pkg)
                except SQLObjectNotFound:
                    return "Cannot find package %s" % package
