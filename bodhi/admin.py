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

from push import PushController
from model import Release

from turbogears import expose, identity
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

    @expose(template='bodhi.templates.text')
    def repotree(self):
        import os
        output = ''
        for release in Release.select():
            for repo in [release.repo, release.testrepo]:
                tree = os.popen('/usr/bin/tree -s %s' % repo)
                output += tree.read() + '\n'
                tree.close()
        return dict(title='Repository Tree', text=output)

