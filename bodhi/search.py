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

from sqlobject.sqlbuilder import LIKE
from turbogears import (expose, paginate, validate, validators, redirect,
                        error_handler, url, flash)
from turbogears.controllers import Controller

from bodhi.model import PackageUpdate, Bugzilla, CVE
from bodhi.widgets import SearchForm

log = logging.getLogger(__name__)

search_form = SearchForm()

class SearchController(Controller):

    @expose(template="bodhi.templates.form")
    def index(self, search=None, tg_errors=None, *args, **kw):
        if tg_errors:
            flash(tg_errors)
        if search:
            raise redirect('/search/%s' % search)
        return dict(form=search_form, values={}, action=url('/search/'),
                    title='Search Updates')

    @expose(template="bodhi.templates.search")
    @validate(validators={"search" : validators.UnicodeString()})
    @error_handler(index)
    @paginate('updates', default_order='-date_submitted',
              limit=20, max_limit=1000)
    def default(self, search, *args, **kw):
        results = set()
        search = search.strip()

        # Search name-version-release
        map(results.add, PackageUpdate.select(
            LIKE(PackageUpdate.q.title, '%%%s%%' % search),
                 orderBy=PackageUpdate.q.date_submitted))

        # Search bug numbers
        try:
            map(lambda bug: map(results.add, bug.updates),
                Bugzilla.select(Bugzilla.q.bz_id==int(search)))
        except ValueError: # can't convert search search to integer
            pass

        # Search CVEs
        if search.startswith('CVE') or search.startswith('CAN'):
            # Search bug titles for CVE, since that is how we track them now
            map(lambda bug: map(results.add, bug.updates),
                Bugzilla.select(LIKE(Bugzilla.q.title, '%%%s%%' % search)))

            # We still have some CVE objects lying around, so search them too
            map(lambda cve: map(results.add, cve.updates),
                CVE.select(CVE.q.cve_id==search))

        # If there is only 1 result, then jump right to it
        num_items = len(results)
        if len(results) == 1:
            raise redirect(results.pop().get_url())

        return dict(updates=list(results), num_items=num_items,
                    title="%d Results Found" % num_items)
