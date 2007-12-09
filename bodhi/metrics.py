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

from datetime import datetime
from turbogears import expose
from turbogears.controllers import Controller
from bodhi.model import PackageUpdate, Release, Package

class Metrics(Controller):

    cache = {} # { graph_type : [data, timestamp] }

    @expose(template='bodhi.templates.metrics')
    def index(self):
        return dict()

    def cache_valid(self, graph):
        """ Return whether or not our metrics cache is valid """
        if self.cache.has_key(graph):
            age = datetime.utcnow() - self.cache[graph][1]
            return age.days < 7

    @expose("json")
    def security(self):
        """
            Return a timeline of security update statistics.
        """
        if self.cache_valid('security'):
            return self.cache['security'][0]
        timeline = {} # { release : { month : # of security updates } }
        months = {}
        for update in PackageUpdate.select(PackageUpdate.q.type == 'security'):
            if update.date_pushed:
                if not timeline.has_key(update.release.name):
                    timeline[update.release.name] = {}
                if not timeline[update.release.name].has_key(update.date_pushed.month):
                    timeline[update.release.name][update.date_pushed.month] = 0
                    months[update.date_pushed.month] = update.date_pushed.strftime("%b")
                for build in update.builds:
                    timeline[update.release.name][update.date_pushed.month] += 1
        for release, data in timeline.items():
            for month, num in data.items():
                if num < 10: # Trim off incomplete months
                    del timeline[release][month]
                    if months.has_key(month):
                        del months[month]
            timeline[release] = timeline[release].items()
        self.cache['security'] = [dict(timeline=timeline, months=months.items()),
                                  datetime.utcnow()]
        return self.cache['security'][0]

    @expose("json")
    def all(self):
        """
            Return a timeline of update statistics for Fedora 7.
        """
        if self.cache_valid('all'):
            return self.cache['all'][0]
        timeline = {} # { type : { month : num } }
        months = {}
        all = {} # { month : num }
        rel = Release.byName('F7')
        for update in PackageUpdate.select(PackageUpdate.q.releaseID == rel.id):
            if update.date_pushed:
                if not timeline.has_key(update.type):
                    timeline[update.type] = {}
                if not timeline[update.type].has_key(update.date_pushed.month):
                    timeline[update.type][update.date_pushed.month] = 0
                    months[update.date_pushed.month] = update.date_pushed.strftime("%b")
                if not all.has_key(update.date_pushed.month):
                    all[update.date_pushed.month] = 0
                for build in update.builds:
                    timeline[update.type][update.date_pushed.month] += 1
                    all[update.date_pushed.month] += 1
        for type, data in timeline.items():
            timeline[type] = data.items()
        for month, num in all.items():
            if num < 100: # trim off incomplete months
                del all[month]
                del months[month]
                for type, data in timeline.items():
                    for m, n in data:
                        if m == month:
                            timeline[type].remove((m, n))
        self.cache['all'] = [dict(timeline=timeline, months=months.items(),
                                  all=all.items()), datetime.utcnow()]
        return self.cache['all'][0]

    @expose("json")
    def most_updated(self):
        """
            Return update statistics by package.
        """
        if self.cache_valid('most_updated'):
            return self.cache['most_updated'][0]
        data = {}
        pkgs = []
        for pkg in Package.select():
            data[pkg.name] = pkg.num_updates()
        items = data.items()
        items.sort(key=lambda x: x[1], reverse=True)
        items = items[:7]
        del data
        data = {}
        for i, item in enumerate(items):
            data[i] = item[1]
            pkgs.append((i + 0.5, item[0]))
        self.cache['most_updated'] = [dict(packages=data.items(), pkgs=pkgs),
                                      datetime.utcnow()]
        return self.cache['most_updated'][0]

    @expose("json")
    def active_devs(self):
        """
            Return update statistics by developer.
        """
        if self.cache_valid('active_devs'):
            return self.cache['active_devs'][0]
        users = {} # { user : # updates }
        data = {}
        for update in PackageUpdate.select():
            if not users.has_key(str(update.submitter)):
                users[str(update.submitter)] = 0
            users[str(update.submitter)] += 1
        items = users.items()
        items.sort(key=lambda x: x[1], reverse=True)
        items = items[:10]
        del users
        users = []
        for i, item in enumerate(items):
            data[i + 0.5] = item[0]
            users.append((i, item[1]))
        self.cache['active_devs'] = [dict(data=users, people=data.items()),
                                     datetime.utcnow()]
        return self.cache['active_devs'][0]
