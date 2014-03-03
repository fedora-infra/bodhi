# $Id: sobzprovider.py,v 1.2 2007/01/03 21:21:18 lmacken Exp $
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
This plugin provides authentication of passwords against Bugzilla via XML-RPC
"""

import logging
import xmlrpclib

from turbogears.identity.soprovider import *
from turbogears import config
from bodhi.model import User, VisitIdentity

log = logging.getLogger(__name__)

class SoBugzillaIdentityProvider(SqlObjectIdentityProvider):
    """
    IdentityProvider that authenticates users against Bugzilla via XML-RPC
    """
    def __init__(self):
        super(SoBugzillaIdentityProvider, self).__init__()
        self.bz_server = config.get('bz_server')

    def validate_identity(self, user_name, password, visit_key):
        newuser = False
        user_name = to_db_encoding(user_name, self.user_class_db_encoding)

        try:
            user = User.by_user_name(user_name)
        except SQLObjectNotFound:
            log.info("Creating new user %s" % user_name)
            user = User(user_name=user_name)
            newuser = True

        if not self.validate_password(user, user_name, password):
            log.warning("Invalid password for %s" % user_name)
            if newuser:
                user.destroySelf()
            return None

        log.info("Login successful for %s" % user_name)

        try:
            link = VisitIdentity.by_visit_key(visit_key)
            link.user_id = user.id
        except SQLObjectNotFound:
            link = VisitIdentity(visit_key=visit_key, user_id=user.id)

        return SqlObjectIdentity(visit_key, user)

    def validate_password(self, user, user_name, password):
        """
        Complete hack, but it works.
        Request bug #1 with the given username and password.  If a Fault is
        thrown, the username/pass is invalid; else, we're good to go.
        """
        # if there is a password in our local database, then authenticate
        # against it (ie, guest, admin, etc)
        if user.password:
            log.debug("Authenticating against local password for %s" % user_name)
            return user.password == self.encrypt_password(password)

        # if there is no password stored, then try the supplied password against
        # bugzilla by attempting to fetch bug #1
        try:
            server = xmlrpclib.Server(self.bz_server)
            server.bugzilla.getBugSimple('1', user_name, password)
        except xmlrpclib.Fault:
            return False
        return True
