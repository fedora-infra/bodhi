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
import util
import logging
import formencode

from os.path import join

from model import Release, Package, PackageUpdate, Bugzilla, CVE
from sqlobject import SQLObjectNotFound

from turbogears import (expose, controllers, validate, validators, flash,
                        error_handler, redirect, identity, config)

from turbogears.widgets import (WidgetsList, TextField, SingleSelectField,
                                CheckBox, TextArea, CalendarDateTimePicker,
                                TableForm, HiddenField, AutoCompleteField)

log = logging.getLogger(__name__)

update_types = ('security', 'bugfix', 'enhancement')

def get_releases():
    return [rel.long_name for rel in Release.select()]

class PackageValidator(validators.FancyValidator):
    messages = {
            'bad_name' : 'Invalid package name; must be in package-version-'
                         'release format',
            'dupe'     : 'Package update %(nvr)s already exists'
    }

    def _to_python(self, value, state):
        return value.strip()

    def validate_python(self, value, state):
        """
        Run basic QA checks on the provided package name
        """
        # Make sure the package is in name-version-release format
        if len(value.split('-') < 3):
            raise Invalid(self.message('bad_name'), value, state)


#class NewUpdateSchema(formencode.Schema):
    #nvr = PackageValidator()
    #release = validators.OneOf(get_releases())
    #testing = validators.Bool()
    #type = validators.OneOf(update_types)
    #embargo = validators.DateTimeConverter()
    #bugs = validators.String()
    #cves = validators.String()
    #notes = validators.String()

## TODO: get package schema/validation working

class UpdateFields(WidgetsList):
    nvr = AutoCompleteField(label='Package', search_controller='/new/pkgsearch',
                            search_param='name', result_name='pkgs')
    release = SingleSelectField(options=get_releases,
                                validator=validators.OneOf(get_releases()))
    testing = CheckBox(validator=validators.Bool)
    type = SingleSelectField(options=update_types,
                             validator=validators.OneOf(update_types))
    embargo = CalendarDateTimePicker(validator=validators.DateTimeConverter())
    bugs = TextField(validator=validators.String())
    cves = TextField(validator=validators.String())
    notes = TextArea(validator=validators.String())
    edited = HiddenField(default=None)

update_form = TableForm(fields=UpdateFields(), submit_text='Submit')

class NewUpdateController(controllers.Controller):

    build_dir = config.get('build_dir')

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def index(self, *args, **kw):
        self.packages = os.listdir(self.build_dir)
        return dict(form=update_form, values={}, action="/save")

    @expose(format="json")
    def pkgsearch(self, name):
        """
        Called automagically by the AutoCompleteWidget.
        Search the build tree for a given package and return a list of
        package-version-release's that are found
        """
        matches = []
        for package in self.packages:
            if package == name:
                for version in os.listdir(join(self.build_dir, package)):
                    for release in os.listdir(join(self.build_dir, package,
                                                   version)):
                        matches.append('-'.join((package, version, release)))
        matches.reverse() # newer version-releases first
        return dict(pkgs = matches)
