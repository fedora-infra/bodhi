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

import re

from formencode import Invalid
from turbogears import validators

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
            vals = value.split()
        elif not isinstance(value['text'], list):
            vals = [value['text']]
        elif isinstance(value['text'], list):
            vals = value['text']
        for build in vals:
            builds += build.replace(',', ' ').split()
        return map(PackageValidator().to_python,
                   map(validators.UnicodeString().to_python,
                       filter(lambda x: x != '', builds)))

class BugValidator(validators.FancyValidator):
    messages = {
            'invalid_bug' : "Invalid bug(s).  Please supply a list of bug "
                            "numbers. Example: 123, 456 #789"
    }

    def _to_python(self, value, state):
        bugs = validators.UnicodeString().to_python(value.strip())
        try:
            bugs = map(int, bugs.replace(',', ' ').replace('#', '').split())
        except ValueError:
            raise Invalid(self.message('invalid_bug', state), bugs, state)
        return bugs

    def validate_python(self, bugs, state):
        for bug in bugs:
            if bug <= 0:
                raise Invalid(self.message('invalid_bug', state), bugs, state)
