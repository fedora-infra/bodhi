# $Id: admin.py,v 1.3 2007/01/08 06:07:07 lmacken Exp $
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
#
# Authors: Luke Macken <lmacken@redhat.com>

import logging
import cherrypy
import simplejson

from Cookie import SimpleCookie
from turbogears import expose, identity, redirect, flash, config
from turbogears.identity import SecureResource
from turbogears.controllers import Controller

from fedora.tg.util import request_format
from fedora.client.proxyclient import ProxyClient

from bodhi.masher import get_masher
from bodhi.model import Release, PackageUpdate


log = logging.getLogger(__name__)

class AdminController(Controller, SecureResource):
    """
    The bodhi administration controller
    """
    require = identity.in_group("releng")

    @expose(template='bodhi.templates.admin')
    def index(self):
        return dict()

    @expose(template='bodhi.templates.masher', allow_json=True)
    def masher(self):
        """ Display the current status of the Masher """
        tags = []
        masher = get_masher()
        for release in Release.select():
            tags.append('%s-updates' % release.dist_tag)
            tags.append('%s-updates-testing' % release.dist_tag)

        return dict(masher_str=str(masher), tags=tags)

    @expose(template='bodhi.templates.text')
    def lastlog(self):
        """ Return the last mash log """
        masher = get_masher()
        (logfile, data) = masher.lastlog()
        return dict(title=logfile, text=data)

    @expose()
    def mash(self, tag):
        """ Kick off a mash for a given tag """
        log.info("Mashing tags: %s" % tag)
        themasher = get_masher()
        themasher.mash_tags([tag])
        raise redirect('/admin/masher')

    @expose(template='bodhi.templates.push', allow_json=True)
    def push(self):
        """ List updates tagged with a push/unpush/move request """
        requests = filter(lambda update: not update.release.locked,
                          PackageUpdate.select(PackageUpdate.q.request != None))
        updates = []
        for update in requests:
            # Skip unapproved security updates
            if update.type == 'security' and not update.approved:
                continue 
            updates.append(update)
        return dict(updates=updates)

    @expose(allow_json=True)
    def mash(self, updates, **kw):
        if request_format() == 'json':
            updates = simplejson.loads(updates.replace("u'", "\"").replace("'", "\""))
        if not isinstance(updates, list):
            updates = [updates]

        if config.get('masher'):
            # Send JSON request with these updates to the masher
            client = ProxyClient(config.get('masher'), debug=True)
            try:
                cookie = SimpleCookie(cherrypy.request.headers.get('Cookie'))
                session, data = client.send_request('/admin/mash',
                                           req_params={'updates': updates},
                                           auth_params={'cookie': cookie})
                if not data.get('success'):
                    flash("Push request was unsuccessful")
                else:
                    flash("Push request sent to masher")
            except Exception, e:
                import traceback
                traceback.print_exc()
                flash("Error while dispatching push: %s" % str(e))
            raise redirect('/admin/masher')

        get_masher().queue([PackageUpdate.byTitle(title) for title in updates])
        return dict(success=True)
        #raise redirect('/admin/masher')
