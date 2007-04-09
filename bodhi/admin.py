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

import os

from os.path import join, isfile
from bodhi.push import PushController

from turbogears import expose, identity, config
from turbogears.identity import SecureResource
from turbogears.controllers import Controller
from turbogears.toolbox.catwalk import CatWalk

class AdminController(Controller, SecureResource):
    require = identity.in_group("admin")

    push = PushController()
    catwalk = CatWalk()

    @expose(template='bodhi.templates.admin')
    def index(self):
        return dict()

    @expose(template='bodhi.templates.repodiff')
    def repodiff(self, diff=None):
        if not diff:
            return dict(diffs=os.listdir(config.get('repodiff_dir')))
        else:
            diff_file = join(config.get('repodiff_dir'), diff)
            if isfile(diff_file):
                diff_file = open(diff_file, 'r')
                output = diff_file.read()
                diff_file.close()
                return dict(tg_template='bodhi.templates.diff', diff=output,
                            title="repodiff - %s" % diff)
            else:
                flash("Invalid repodiff specified: %s" % diff)
        raise redirect('/admin')
