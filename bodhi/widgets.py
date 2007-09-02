# $Id: $
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

from bodhi.model import Release, releases
from formencode import Invalid
from turbogears import validators, url, config
from turbogears.widgets import (Form, TextField, SubmitButton, TextArea,
                                AutoCompleteField, SingleSelectField, CheckBox,
                                HiddenField, RadioButtonList)

class CommentForm(Form):
    template = "bodhi.templates.commentform"
    submit_text = "Add Comment"
    fields = [
            TextArea(name='text', label='',
                     validator=validators.UnicodeString(),
                     rows=3, cols=40),
            HiddenField(name='title'),
            # We're currently hardcoding the karma radio buttons by hand in the
            # commentform template, because the RadioButtonList is ugly
    ]

class SearchForm(Form):
    template = "bodhi.templates.searchform"
    fields = [
            TextField("search", default="  Package | Bug # | CVE  ",
                      attrs={ 'size' : 20 }),
    ]

class PackageValidator(validators.FancyValidator):
    messages = {
            'bad_name' : 'Invalid package name; must be in package-version-'
                         'release format',
    }

    def _to_python(self, value, state):
        return value.strip()

    def validate_python(self, value, state):
        # We eventually should check the koji tag of each package in this
        # validator, but in that case we need to know what release this update
        # is being submitted for.
        if len(value.split('-')) < 3:
            raise Invalid(self.message('bad_name', state), value, state)

class AutoCompleteValidator(validators.Schema):
    def _to_python(self, value, state):
        vals = []
        builds = []
        if isinstance(value, str):
            vals = [value]
        elif not isinstance(value['text'], list):
            vals = [value['text']]
        elif isinstance(value['text'], list):
            vals = value['text']
        for build in vals:
            builds += build.split(',')
        return map(PackageValidator().to_python,
                   map(validators.UnicodeString().to_python,
                       filter(lambda x: x != '', builds)))

def get_release_names():
    return [rel[1] for rel in releases()]

def get_release_tuples():
    # Create a list of each releases 'name' and
    # 'long_name' to choose from.  We do this
    # to allow the command-line client to use
    # short release names.
    return sum(zip(*releases())[:2], ())

class NewUpdateForm(Form):
    template = "bodhi.templates.new"
    submit_text = "Add Update"
    update_types = config.get('update_types', 'bugfix enhancement security').split()
    fields = [
            AutoCompleteField('builds', label='Package',
                              search_controller=url('/new/search'),
                              search_param='name', result_name='pkgs',
                              template='bodhi.templates.packagefield',
                              validator=AutoCompleteValidator()),
            TextField('build', validator=validators.UnicodeString(),
                      attrs={'style' : 'display: none'}),
            SingleSelectField('release', options=get_release_names,
                              validator=validators.OneOf(get_release_tuples)),
            SingleSelectField('type', options=update_types,
                              validator=validators.OneOf(update_types)),
            TextField('bugs', validator=validators.UnicodeString()),
            TextField('cves', validator=validators.UnicodeString()),
            TextArea('notes', validator=validators.UnicodeString(),
                     rows=20, cols=65),
            CheckBox(name='close_bugs', help_text='Automatically close bugs',
                     default=True),
            HiddenField('edited', default=None),
    ]

