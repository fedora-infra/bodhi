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

from os.path import join
from bodhi.model import Release
from turbogears import expose, controllers, validators, identity, config, url
from turbogears.widgets import (TextField, SingleSelectField, TextArea, Form,
                                HiddenField, AutoCompleteField, SubmitButton,
                                CheckBox)

update_types = config.get('update_types', 'bugfix enhancement security').split()

def get_releases():
    return [rel.long_name for rel in Release.select()]

class NewUpdateForm(Form):
    template = "bodhi.templates.new"
    fields = [
            AutoCompleteField('build', label='Package',
                              search_controller=url('/new/search'),
                              search_param='name', result_name='pkgs',
                              # We're hardcoding the template to fix Ticket #32
                              # until the AutoCompleteField can work properly
                              # under sub-controllers
                              template='bodhi.templates.packagefield'),
            TextField('builds', validator=validators.UnicodeString(),
                      attrs={'style' : 'display: none'}),
            SingleSelectField('release', options=get_releases,
                              validator=validators.OneOf(get_releases())),
            SingleSelectField('type', options=update_types,
                              validator=validators.OneOf(update_types)),
            TextField('bugs', validator=validators.UnicodeString()),
            TextField('cves', validator=validators.UnicodeString()),
            TextArea('notes', validator=validators.UnicodeString(),
                     rows=20, cols=75),
            CheckBox(name='close_bugs', help_text='Automatically close bugs'),
            HiddenField('edited', default=None),
    ]

update_form = NewUpdateForm(submit_text='Add Update',
                            form_attrs={
                                 'onsubmit' :
                                   "$('bodhi-logo').style.display = 'none';"
                                   "$('wait').style.display = 'block';"
                            })

class NewUpdateController(controllers.Controller):

    build_dir = config.get('build_dir')
    packages  = None

    def build_pkglist(self):
        """ Cache a list of packages used for the package AutoCompleteField """
        self.packages = os.listdir(self.build_dir)

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def index(self, *args, **kw):
        self.build_pkglist()
        return dict(form=update_form, values={}, action=url("/save"))

    @expose(format="json")
    def search(self, name):
        """
        Called automagically by the AutoCompleteWidget.
        If a package is specified (or 'pkg-'), return a list of available
        n-v-r's.  This method also auto-completes packages.
        """
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
