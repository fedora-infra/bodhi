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

from tgcaptcha import CaptchaField
from turbogears import validators, url, config
from turbogears.widgets import (Form, TextField, SubmitButton, TextArea,
                                AutoCompleteField, SingleSelectField, CheckBox,
                                HiddenField, RemoteForm, CheckBoxList, JSLink,
                                DataGrid, CSSLink)

from bodhi.util import make_update_link
from bodhi.validators import *

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

class CommentCaptchaForm(Form):
    template = "bodhi.templates.captchacommentform"
    submit_text = "Add Comment"
    fields = [
            TextArea(name='text', label='',
                     validator=validators.All(
                         validators.NotEmpty(),
                         validators.UnicodeString()),
                     rows=3, cols=40),
            HiddenField(name='title',
                        validator=validators.All(
                            validators.NotEmpty(),
                            validators.UnicodeString())),
            TextField(name='author', label='Author',
                      default='E-Mail Address',
                      validator=validators.Email()),
            CaptchaField(name='captcha', label='Enter the code shown')
    ]

class SearchForm(Form):
    template = "bodhi.templates.searchform"
    fields = [
            TextField("search", default="  Package | Bug # | CVE  ",
                      attrs={ 'size' : 25 }),
    ]

class LocalJSLink(JSLink):
    """ Link to local Javascript files """
    def update_params(self, d):
        super(LocalJSLink, self).update_params(d)
        d["link"] = url(self.name)

class LocalCSSLink(CSSLink):
    """ Link to local CSS files """
    def update_params(self, d):
        super(LocalCSSLink, self).update_params(d)
        d["link"] = url(self.name)

class NewUpdateForm(Form):
    template = "bodhi.templates.new"
    submit_text = "Save Update"
    update_types = config.get('update_types').split()
    request_types = ['Testing', 'Stable', 'None', None]
    fields = [
            AutoCompleteField('builds', label='Package',
                              search_controller=url('/new/search'),
                              search_param='name', result_name='pkgs',
                              template='bodhi.templates.packagefield',
                              validator=AutoCompleteValidator()),
            CheckBox('inheritance', label='Follow Build inheritance',
                     validator=validators.StringBool(),
                     default=False, attrs={'title' : 'Build Inheritance - '
                                                     'TODO'}),
            SingleSelectField('type_', label='Type', options=update_types,
                              validator=validators.OneOf(update_types)),
            SingleSelectField('request', options=request_types,
                              validator=validators.OneOf(request_types +
                                  [r.lower() for r in request_types if r])),
            TextField('bugs', validator=BugValidator(),
                      attrs={'title' : 'Bug Numbers - A space or comma '
                                       'delimited list of bug numbers or '
                                       'aliases.  Example: #1234, 789 '
                                       'CVE-2008-0001'}),
            TextArea('notes', validator=validators.UnicodeString(),
                     rows=13, cols=65,
                     attrs={'title' : 'Advisory Notes - Some optional details '
                                      'about this update that will appear in '
                                      'the notice'}),
            CheckBox(name='close_bugs', help_text='Automatically close bugs',
                     validator=validators.StringBool(),
                     default=True, attrs={'title' : 'Close Bugs - '
                                                    'Automatically close bugs '
                                                    'when this update is '
                                                    'pushed as stable'}),
            HiddenField('edited', default=None),
            CheckBox(name='suggest_reboot', label='Suggest Reboot',
                     validator=validators.StringBool(),
                     default=False, attrs={'title': 'Suggest Reboot - '
                                                    'Recommend that the user '
                                                    'restarts their machine '
                                                    'after installing this '
                                                    'update'}),
            CheckBox(name='autokarma', label='Enable karma automatism',
                     default=True, validator=validators.StringBool(),
                     attrs={'onclick':
                         '$("#form_stable_karma").attr("disabled", !$("#form_stable_karma").attr("disabled"));'
                         '$("#form_unstable_karma").attr("disabled", !$("#form_unstable_karma").attr("disabled"));',
                    'title': 'Karma Automatism - Enable update request '
                             'automation based on user feedback',
            }),
            TextField('stable_karma', label='Threshold for pushing to stable',
                      validator=validators.Int(), default='3',
                      attrs={'title' : 'Stable Karma - The threshold for '
                             'automatically pushing this update to stable',
                             'size' : '1'}),
            TextField('unstable_karma', label='Threshold for unpushing',
                      validator=validators.Int(), default='-3',
                      attrs={'title' : 'Unstable Karma - The threshold for '
                             'automatically unpushing an unstable update',
                             'size' : '1'})
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
        class="okcancelform">
        <div >
            <div py:content="ok.display('Ok')" />
            <div py:content="cancel.display('Cancel')" />
        </div>
    </form>
    """

class ObsoleteForm(RemoteForm):
    """
    A jQuery UI dialog that presents the user with a list of pending/testing
    updates for a given package.  The user is then able to instantly obsolete
    any of them with the click of a button.
    """
    action = url('/obsolete')
    update = 'post_data'
    submit_text = "Obsolete"

    def __init__(self, builds):
        super(ObsoleteForm, self).__init__()
        options = [(build.nvr, make_update_link(build)) for build in builds]
        self.fields = [
            CheckBoxList("updates", label="", options=options,
                         default=[build.nvr for build in builds])
        ]

class SortableDataGrid(DataGrid):
    template = "bodhi.templates.sortabletable"
    javascript = [LocalJSLink('bodhi', '/static/js/jquery.js'),
                  LocalJSLink('bodhi', '/static/js/jquery.tablesorter.js')]
    css = [LocalCSSLink('bodhi', '/static/css/flora.tablesorter.css')]
