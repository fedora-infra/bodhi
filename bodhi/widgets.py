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

from bodhi.model import Release
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
            #SubmitButton("submit", default="Search")
    ]

class AutoCompleteValidator(validators.Schema):
    def _to_python(self, value, state):
        return validators.UnicodeString().to_python(value['text'])

def get_releases():
    return [rel.long_name for rel in Release.select()]

update_types = config.get('update_types', 'bugfix enhancement security').split()

class NewUpdateForm(Form):
    template = "bodhi.templates.new"
    fields = [
            AutoCompleteField('build', label='Package',
                              search_controller=url('/new/search'),
                              search_param='name', result_name='pkgs',
                              # We're hardcoding the template to fix Ticket #32
                              # until the AutoCompleteField can work properly
                              # under sub-controllers
                              template='bodhi.templates.packagefield',
                              validator=AutoCompleteValidator()),
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
