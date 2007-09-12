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

from bodhi.util import get_release_names, get_release_tuples
from bodhi.validators import *

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

class NewUpdateForm(Form):
    template = "bodhi.templates.new"
    submit_text = "Add Update"
    update_types = config.get('update_types').split()
    fields = [
            AutoCompleteField('builds', label='Package',
                              search_controller=url('/new/search'),
                              search_param='name', result_name='pkgs',
                              template='bodhi.templates.packagefield',
                              validator=AutoCompleteValidator()),
            SingleSelectField('release', options=get_release_names,
                              validator=validators.OneOf(get_release_tuples())),
            SingleSelectField('type', options=update_types,
                              validator=validators.OneOf(update_types)),
            TextField('bugs', validator=BugValidator(),
                      attrs={'title' : 'A space or comma delimieted list of ' +
                                       'bug numbers.  Example: #1234, 56 789'}),
            TextField('cves', validator=CVEValidator(), label='CVEs',
                      attrs={'title' : 'A space or comma delimieted list of ' +
                                       'CVE IDs.'}),
            TextArea('notes', validator=validators.UnicodeString(),
                     rows=20, cols=65,
                     attrs={'title' : 'Some optional details about this ' +
                                      'update that will appear in the notice'}),
            CheckBox(name='close_bugs', help_text='Automatically close bugs',
                     default=True),
            HiddenField('edited', default=None),
    ]

class OkCancelForm(Form):
    name = "okcancelform"
    member_widgets = ["ok", "cancel"]
    params = ["action", "method"]
    ok = SubmitButton('ok')
    cancel = SubmitButton('cancel')
    
    template = """
    <form xmlns:py="http://purl.org/kid/ns#"
        name="${name}"
        action="${action}"
        method="${method}"
        class="okcancelform"
    >
        <div >
            <div py:content="ok.display('Ok')" />
            <div py:content="cancel.display('Cancel')" />
        </div>
    </form>
    """