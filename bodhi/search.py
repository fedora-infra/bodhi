# $Id: new.py,v 1.8 2007/01/06 08:03:21 lmacken Exp $
#
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

import logging

from model import PackageUpdate, Bugzilla, CVE
from exceptions import ValueError
from sqlobject.sqlbuilder import LIKE
from turbogears import (expose, identity, paginate, validate,
                        validators, redirect)
from turbogears.widgets import TextField, Form, Button
from turbogears.controllers import Controller

log = logging.getLogger(__name__)

class SearchController(Controller):

    class SearchForm(Form):
        template = "bodhi.templates.searchform"
        fields = [
                TextField("search"),
                Button("submit", default="Search", attrs={'type':'submit'})
        ]

    search_form = SearchForm()

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def index(self, search=None, *args, **kw):
        if search:
            raise redirect('/search/%s' % search)
        return dict(form=self.search_form, values={}, action='/search/')

    @expose(template="bodhi.templates.list")
    @identity.require(identity.not_anonymous())
    @validate(validators={ "search"  : validators.String() })
    @paginate('updates', default_order='update_id', limit=15)
    def default(self, search, *args, **kw):
        results = set()

        # Search name-version-release
        map(results.add, PackageUpdate.select(LIKE(PackageUpdate.q.nvr,
                                                   '%%%s%%' % search)))

        # Search bug numbers
        try:
            map(lambda bug: map(results.add, bug.updates),
                Bugzilla.select(Bugzilla.q.bz_id==int(search)))
        except ValueError: # can't convert search search to integer
            pass

        # Search CVE's
        if search.startswith('CVE') or search.startswith('CAN'):
            map(lambda cve: map(results.add, cve.updates),
                CVE.select(CVE.q.cve_id==search))

        return dict(updates=list(results), tg_template="bodhi.templates.list")
