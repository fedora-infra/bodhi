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

import os
import logging
import tempfile
import cherrypy
import commands

from datetime import datetime
from turbogears import expose, redirect, config, identity, controllers
from bodhi.model import PackageUpdate
from os.path import join

log = logging.getLogger(__name__)

class PushController(controllers.Controller, identity.SecureResource):
    require = identity.in_group("releng")

    def __init__(self):
        self.orig_repo = None

    def repodiff(self):
        """
        When this method is first called, it saves a snapshot of the
        updates-stage tree (tree -s output).  When called a second time,
        it takes another snapshot, diffs it with the original, and stores
        the diff in 'repodiff_dir'.
        """
        if not self.orig_repo:
            self.orig_repo = tempfile.mkstemp()
            tree = commands.getoutput("tree -s %s" % self.stage_dir)
            os.write(self.orig_repo[0], tree)
        else:
            self.new_repo = tempfile.mkstemp()
            tree = commands.getoutput("tree -s %s" % self.stage_dir)
            os.write(self.new_repo[0], tree)
            os.close(self.new_repo[0])
            os.close(self.orig_repo[0])
            diff = join(config.get('repodiff_dir'), '%s' %
                        datetime.utcnow().strftime("%Y%m%d-%H%M%S"))
            diff = open(diff, 'w')
            diff.write(commands.getoutput("diff -u %s %s" % (self.orig_repo[1],
                                                             self.new_repo[1])))
            diff.close()
            os.unlink(self.orig_repo[1])
            os.unlink(self.new_repo[1])
            self.orig_repo = None

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
