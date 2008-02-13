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

import random
import simplejson

from turbogears import validators, url, config
from turbogears.widgets import (Form, TextField, SubmitButton, TextArea,
                                AutoCompleteField, SingleSelectField, CheckBox,
                                HiddenField, RemoteForm, CheckBoxList, JSLink,
                                Widget)

from bodhi.util import get_release_names, get_release_tuples, make_update_link
from bodhi.validators import *

from tgcaptcha import CaptchaField

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
                      default='Anonymous Tester',
                      validator=validators.All(
                          validators.NotEmpty(),
                          validators.UnicodeString())),
            CaptchaField(name='captcha', label='Enter the code shown')
    ]

class SearchForm(Form):
    template = "bodhi.templates.searchform"
    fields = [
            TextField("search", default="  Package | Bug # | CVE  ",
                      attrs={ 'size' : 25 }),
    ]

class LocalJSLink(JSLink):
    """
    Link to local Javascript files
    """
    def update_params(self, d):
        super(JSLink, self).update_params(d)
        d["link"] = url(self.name)

class AutoCompletePackage(AutoCompleteField):
    javascript = [LocalJSLink('bodhi', '/static/js/MochiKit.js'),
                  JSLink("turbogears.widgets","autocompletefield.js")]

class NewUpdateForm(Form):
    template = "bodhi.templates.new"
    submit_text = "Save Update"
    update_types = config.get('update_types').split()
    request_types = ['Testing', 'Stable', 'None']
    fields = [
            AutoCompletePackage('builds', label='Package',
                                search_controller=url('/new/search'),
                                search_param='name', result_name='pkgs',
                                template='bodhi.templates.packagefield',
                                validator=AutoCompleteValidator()),
            SingleSelectField('release', options=get_release_names,
                              validator=validators.OneOf(get_release_tuples())),
            SingleSelectField('type', options=update_types,
                              validator=validators.OneOf(update_types)),
            SingleSelectField('request', options=request_types,
                              validator=validators.OneOf( request_types +
                                  [r.lower() for r in request_types])),
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
                     default=True, attrs={'title' : 'Close Bugs - '
                                                    'Automatically close bugs '
                                                    'when this update is '
                                                    'pushed as stable'}),
            HiddenField('edited', default=None),
            CheckBox(name='suggest_reboot', label='Suggest Reboot',
                     default=False)
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
        super(RemoteForm, self).__init__()
        options = [(build.nvr, make_update_link(build)) for build in builds]
        self.fields = [
            CheckBoxList("updates", label="", options=options,
                         default=[build.nvr for build in builds])
        ]


class TurboFlot(Widget):
    """
        A TurboGears Flot Widget.
    """
    template = """
      <div xmlns:py="http://purl.org/kid/ns#" id="turboflot${id}"
           style="width:${width};height:${height};">
        <script>
          $.plot($("#turboflot${id}"), ${data}, ${options});
        </script>
      </div>
    """
    params = ["data", "options", "height", "width", "id"]
    params_doc = {
            "data"    : "An array of data series",
            "options" : "Plot options",
            "height"  : "The height of the graph",
            "width"   : "The width of the graph"
    }
    javascript = [LocalJSLink("bodhi", "/static/js/excanvas.js"),
                  LocalJSLink("bodhi", "/static/js/jquery.js"),
                  LocalJSLink("bodhi", "/static/js/jquery.flot.js")]

    def __init__(self, data, options={}, height="300px", width="600px"):
        random.seed()
        self.id = str(int(random.random() * 1000))
        self.data = simplejson.dumps(data)
        self.options = simplejson.dumps(options)
        self.height = height
        self.width = width
