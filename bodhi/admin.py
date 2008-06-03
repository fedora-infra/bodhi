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

import logging

from bodhi.push import PushController
from bodhi.masher import get_masher
from bodhi.model import Release

from turbogears import expose, identity, redirect
from turbogears.identity import SecureResource
from turbogears.controllers import Controller

log = logging.getLogger(__name__)

class AdminController(Controller, SecureResource):
    require = identity.in_group("releng")

    push = PushController()

    @expose(template='bodhi.templates.admin')
    def index(self):
        return dict()

    @expose(template='bodhi.templates.masher', allow_json=True)
    def masher(self, lastlog=None):
        """
        Display the current status of the Masher
        """
        m = get_masher()
        if lastlog:
            (logfile, data) = m.lastlog()
            return dict(title=logfile, text=data,
                        tg_template='bodhi.templates.text')

        tags = []
        for release in Release.select():
            tags.append('%s-updates' % release.dist_tag)
            tags.append('%s-updates-testing' % release.dist_tag)

        return dict(masher_str=str(m), tags=tags)

    @expose()
    def mash(self, tag):
        log.info("Mashing tags: %s" % tag)
        m = get_masher()
        m.mash_tags([tag])
        raise redirect('/admin/masher')
