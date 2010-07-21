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
import logging

from os.path import join
from operator import itemgetter
from turbogears import expose, controllers, identity, config, flash

from bodhi.widgets import NewUpdateForm
from bodhi.buildsys import get_session
from bodhi.model import Release
from bodhi.util import url

log = logging.getLogger(__name__)
update_form = NewUpdateForm()

packages = []

# Load the list of packages from koji
if config.get('buildsystem') == 'koji':
    try:
        koji = get_session()
        packages = [pkg['package_name'] for pkg in koji.listPackages()]
        log.debug("%d packages loaded from koji" % len(packages))
    except Exception, e:
        log.exception(e)
        log.error("There was a problem loading the package list from koji")
else:
    # Resort to looking on the filesystem for the package names
    try:
        packages = os.listdir(config.get('build_dir'))
    except (OSError, TypeError):
        log.warning("Warning: build_dir either invalid or not set in app.cfg")


class NewUpdateController(controllers.Controller):

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def index(self, *args, **kw):
        notice = config.get('newupdate_notice')
        if notice:
            flash(notice)
        return dict(form=update_form, values=kw, action=url("/save"),
                    title='New Update Form')

    @expose(format="json")
    def search(self, name):
        """
        Called automagically by the AutoCompleteWidget.
        If a package is specified (or 'pkg-'), return a list of available
        n-v-r's.  This method also auto-completes packages.
        """
        if not name: return dict()
        matches = []
        pkgname = name[:-1]
        if name[-1] == '-' and pkgname and pkgname in packages:
            name = pkgname
            matches.extend(self._fetch_candidate_builds(pkgname))
        else:
            for pkg in packages:
                if name == pkg:
                    matches.extend(self._fetch_candidate_builds(pkg))
                    break
                elif pkg.startswith(name):
                    matches.append(pkg)
        return dict(pkgs=matches)

    def _fetch_candidate_builds(self, pkg):
        """ Return all candidate builds for a given package """
        matches = {}
        koji = get_session()
        koji.multicall = True
        for tag in [r.candidate_tag for r in Release.select()]:
            koji.getLatestBuilds(tag, package=pkg)
        results = koji.multiCall()
        for result in results:
            for entries in result:
                for entry in entries:
                    matches[entry['nvr']] = entry['completion_time']
        return [build[0] for build in
                sorted(matches.items(), key=itemgetter(1), reverse=True)]
