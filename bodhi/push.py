# $Id: push.py,v 1.5 2007/01/08 06:07:07 lmacken Exp $
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

from turbogears import expose, redirect, identity, controllers
from bodhi.model import PackageUpdate

log = logging.getLogger(__name__)

class PushController(controllers.Controller, identity.SecureResource):
    require = identity.in_group("releng")

    @expose(template='bodhi.templates.push', allow_json=True)
    def index(self):
        """ List updates tagged with a push/unpush/move request """
        updates = filter(lambda update: not update.release.locked,
                         PackageUpdate.select(PackageUpdate.q.request != None))
        return dict(updates=updates)

    @expose(allow_json=True)
    def mash(self, updates, **kw):
        from bodhi.masher import masher
        if 'tg_format' in cherrypy.request.params and \
                cherrypy.request.params['tg_format'] == 'json':
            import simplejson
            updates = simplejson.loads(updates.replace("'", "\""))
        if not isinstance(updates, list):
            updates = [updates]
        masher.queue([PackageUpdate.byTitle(title) for title in updates])
        raise redirect('/admin/masher')
