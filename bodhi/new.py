# $Id: new.py,v 1.8 2007/01/06 08:03:21 lmacken Exp $
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

from os.path import join
from bodhi.widgets import NewUpdateForm
from turbogears import expose, controllers, identity, config, url, flash

log = logging.getLogger(__name__)
update_form = NewUpdateForm()

class NewUpdateController(controllers.Controller):

    build_dir = config.get('build_dir')
    packages  = []

    def build_pkglist(self):
        """ Cache a list of packages used for the package AutoCompleteField """
        try:
            self.packages = os.listdir(self.build_dir)
        except (OSError, TypeError):
            log.warning("Warning: build_dir either invalid or not set in app.cfg")

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def index(self, *args, **kw):
        self.build_pkglist()
        return dict(form=update_form, values=kw, action=url("/save"),
                    title='New Update Form')

    @expose(format="json")
    def search(self, name):
        """
        Called automagically by the AutoCompleteWidget.
        If a package is specified (or 'pkg-'), return a list of available
        n-v-r's.  This method also auto-completes packages.
        """
        if not name: return dict()
        matches = []
        if not self.packages: self.build_pkglist()
        if name[-1] == '-' and name[:-1] and name[:-1] in self.packages:
            name = name[:-1]
            for version in os.listdir(join(self.build_dir, name)):
                for release in os.listdir(join(self.build_dir, name, version)):
                    matches.append('-'.join((name, version, release)))
        else:
            for pkg in self.packages:
                if name == pkg:
                    for version in os.listdir(join(self.build_dir, name)):
                        for release in os.listdir(join(self.build_dir, name,
                                                       version)):
                            matches.append('-'.join((name, version, release)))
                    break
                elif pkg.startswith(name):
                    matches.append(pkg)
        matches.reverse()
        return dict(pkgs=matches)
