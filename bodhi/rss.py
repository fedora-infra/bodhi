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

from turbogears.feed import FeedController
from turbogears import expose, config
from sqlobject.sqlbuilder import AND

from bodhi.model import Release, PackageUpdate

class Feed(FeedController):

    def get_feed_data(self, release=None, type=None, status=None, *args, **kw):
        entries = []
        query = []

        if release:
            rel = Release.byName(release.upper())
            query.append(PackageUpdate.q.releaseID == rel.id)
        if type:
            query.append(PackageUpdate.q.type == type)
        if status:
            query.append(PackageUpdate.q.status == status)
        query.append(PackageUpdate.q.pushed == True)

        updates = PackageUpdate.select(AND(*query),
                        orderBy=PackageUpdate.q.date_pushed).reversed()[:20]

        for update in updates:
            entries.append({
                'date_released' : update.date_pushed,
                'title'   : "%s %sUpdate: %s" % (update.release.long_name,
                                                 update.type == 'security'
                                                 and 'Security ' or '',
                                                 update.title),
                'author'  : update.submitter,
                'link'    : config.get('base_address') + update.get_url(),
                'summary' : update.notes
            })
            if len(update.bugs):
                bugs = "<b>Resolved Bugs</b><br/>"
                for bug in update.bugs:
                    bugs += "<a href=%s>%d</a> - %s<br/>" % (bug.get_url(), bug.bz_id, bug.title)
                entries[-1]['summary'] = "%s<br/>%s" % (bugs[:-2], entries[-1]['summary'])


        return dict(
                title = "Fedora Updates",
                link = config.get('base_address'),
                entries = entries
        )
