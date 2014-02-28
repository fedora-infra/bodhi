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

from datetime import datetime
from turbogears.feed import FeedController
from turbogears import config, url
from sqlobject import SQLObjectNotFound
from sqlobject.sqlbuilder import AND, OR

from bodhi.model import Release, PackageUpdate, Comment, Package

log = logging.getLogger(__name__)

class Feed(FeedController):

    def get_feed_data(self, release=None, type=None, status=None,
                      comments=False, submitter=None, builds=None,
                      user=None, package=None, critpath=False,
                      unapproved=None, *args, **kw):
        query = []
        entries = []
        date = lambda update: update.date_pushed
        order = PackageUpdate.q.date_pushed
        title = []
        critpath = critpath in (True, 'True', 'true')
        unapproved = unapproved in (True, 'True', 'true')

        if critpath:
            return self.get_critpath_updates(release=release,
                                             unapproved=unapproved)
        if comments:
            return self.get_latest_comments(user=user)
        if package:
            return self.get_package_updates(package, release)
        if release:
            try:
                rel = Release.byName(release.upper())
            except SQLObjectNotFound:
                return dict(title = '%s not found' % release, entries=[])
            query.append(PackageUpdate.q.releaseID == rel.id)
            title.append(rel.long_name)
        if type:
            query.append(PackageUpdate.q.type == type)
            title.append(type.title())
        if status:
            query.append(PackageUpdate.q.status == status)
            if status == 'pending':
                date = lambda update: update.date_submitted
                order = PackageUpdate.q.date_submitted
            else:
                # Let's only show pushed testing/stable updates
                query.append(PackageUpdate.q.pushed == True)
            title.append(status.title())
        else:
            query.append(PackageUpdate.q.pushed == True)

        if submitter:
            query.append(PackageUpdate.q.submitter == submitter)
            title.append("submitted by %s" % submitter)

        if builds:
            query.append(PackageUpdate.q.builds == builds)
            title.append("for %s" % builds)

        updates = PackageUpdate.select(AND(*query), orderBy=order).reversed()

        for update in updates:
            delta = datetime.utcnow() - update.date_submitted
            if delta and delta.days > config.get('feeds.num_days_to_show'):
                if len(entries) >= config.get('feeds.max_entries'):
                    break
            entries.append({
                'id'        : config.get('base_address') + url(update.get_url()),
                'summary'   : update.notes,
                'published' : date(update),
                'link'      : config.get('base_address') + url(update.get_url()),
                'title'     : "%s %sUpdate: %s" % (update.release.long_name,
                                                   update.type == 'security'
                                                   and 'Security ' or '',
                                                   update.title)
            })
            if len(update.bugs):
                bugs = "<b>Resolved Bugs</b><br/>"
                for bug in update.bugs:
                    bugs += "<a href=%s>%d</a> - %s<br/>" % (bug.get_url(),
                                                             bug.bz_id, bug.title)
                entries[-1]['summary'] = "%s<br/>%s" % (bugs[:-2],
                                                        entries[-1]['summary'])

        title.append('Updates')

        return dict(
                title = ' '.join(title),
                subtitle = "",
                link = config.get('base_address') + url('/'),
                entries = entries
        )

    def get_latest_comments(self, user=None):
        entries = []
        if user:
            comments = Comment.select(Comment.q.author == user,
                    orderBy=Comment.q.timestamp).reversed()
        else:
            comments = Comment.select(Comment.q.author != 'bodhi',
                    orderBy=Comment.q.timestamp).reversed()
        for comment in comments:
            delta = datetime.utcnow() - comment.update.date_submitted
            if delta and delta.days > config.get('feeds.num_days_to_show'):
                if len(entries) >= config.get('feeds.max_entries'):
                    break

            entries.append({
                'id'        : config.get('base_address') +
                              url(comment.update.get_url()),
                'summary'   : comment.text,
                'published' : comment.timestamp,
                'link'      : config.get('base_address') +
                              url(comment.update.get_url()),
                              'title'     : "[%s] [%s] [%d]" % (
                                  comment.update.title, comment.author,
                                  comment.karma)
            })
        return dict(
                title = 'Latest Comments',
                subtitle = "",
                link = config.get('base_address') + url('/'),
                entries = entries,
        )

    def get_package_updates(self, package, release):
        entries = []
        pkg = Package.byName(package)
        base = config.get('base_address')
        for i, update in enumerate(pkg.updates()):
            delta = datetime.utcnow() - update.date_submitted
            if delta and delta.days > config.get('feeds.num_days_to_show'):
                if len(entries) >= config.get('feeds.max_entries'):
                    break

            if release and not update.release.name == release:
                continue

            entries.append({
                'id'        : base + url(update.get_url()),
                'summary'   : update.notes,
                'link'      : base + url(update.get_url()),
                'published' : update.date_submitted,
                'updated'   : update.date_submitted,
                'title'     : update.title,
            })
        return dict(
                title = 'Latest Updates for %s' % package,
                subtitle = "",
                link = config.get('base_address') + url('/'),
                entries = entries
        )

    def get_critpath_updates(self, release=None, unapproved=None):
        i = 0
        entries = []
        base = config.get('base_address')
        title = 'Latest Critical Path Updates'
        query = [PackageUpdate.q.status != 'obsolete']
        if release:
            try:
                release = Release.byName(release)
            except SQLObjectNotFound:
                return dict(title = '%s release not found' % release, entries=[])
            releases = [release]
            title = title + ' for %s' % release.long_name
        else:
            releases = Release.select()
        if unapproved:
            query.append(PackageUpdate.q.status != 'stable')
        for update in PackageUpdate.select(
                AND(OR(*[PackageUpdate.q.releaseID == release.id
                         for release in releases]),
                    *query),
                orderBy=PackageUpdate.q.date_submitted).reversed():

            delta = datetime.utcnow() - update.date_submitted
            if delta and delta.days > config.get('feeds.num_days_to_show'):
                if len(entries) >= config.get('feeds.max_entries'):
                    break

            if update.critpath:
                if unapproved:
                    if update.critpath_approved:
                        continue
                entries.append({
                    'id'        : base + url(update.get_url()),
                    'summary'   : update.notes,
                    'link'      : base + url(update.get_url()),
                    'published' : update.date_submitted,
                    'updated'   : update.date_submitted,
                    'title'     : update.title,
                })
                i += 1
        return dict(
                title = title,
                subtitle = "",
                link = config.get('base_address') + url('/'),
                entries = entries
        )
