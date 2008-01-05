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
from bodhi.widgets import TurboFlot

class Metrics(Controller):

    cache = {} # { graph_type : [data, timestamp] }

    @expose(template='bodhi.templates.metrics')
    def index(self):
        all_data = self.all()
        all = TurboFlot([
            {
                'data'  : all_data['all'],
                'label' : 'All Updates',
                'bars'  : { 'show' : 'true' }
            },
            {
                'data'  : all_data['timeline']['bugfix'],
                'label' : 'Bugfix',
                'lines'  : { 'show' : 'true' },
                'points' : { 'show' : 'true' }
            },
            {
                'data'   : all_data['timeline']['enhancement'],
                'label'  : 'Enhancement',
                'lines'  : { 'show' : 'true' },
                'points' : { 'show' : 'true' }
            },
            {
                'data' : all_data['timeline']['security'],
                'label' : 'Security',
                'lines' : { 'show' : 'true' },
                'points' : { 'show' : 'true' }
            }],
            {
                'grid' : { 'backgroundColor' : '#fffaff' },
                'xaxis' : { 'ticks' : all_data['months'] },
                'yaxis' : { 'max' : '850' }
            }
        )

        security_data = self.security()
        security = TurboFlot([
            {
                'data'  : security_data['timeline']['F7'],
                'lines' : { 'show' : 'true' }
            }],
            {
                'grid'  : { 'backgroundColor' : '#fffaff' },
                'xaxis' : { 'ticks' : security_data['months'] }
            }
        )

        most_data = self.most_updated()
        most_updates = TurboFlot([
            # Hack to get the color we want :)
            { 'data' : [[0,0]] }, { 'data' : [[0,0]] }, { 'data' : [[0,0]] },
            { 'data' : [[0,0]] }, { 'data' : [[0,0]] }, { 'data' : [[0,0]] },
            {
                'data' : most_data['packages'],
                'bars' : { 'show' : 'true' }
            }],
            {
                'grid'  : { 'backgroundColor' : '#fffaff' },
                'xaxis' : { 'ticks' : most_data['pkgs'] }
            }
        )

        active_devs_data = self.active_devs()
        active_devs = TurboFlot([
            { 'data' : [[0,0]] }, { 'data' : [[0,0]] }, { 'data' : [[0,0]] },
            {
                'data' : active_devs_data['data'],
                'bars' : { 'show' : 'true' }
            }],
            {
                'grid' : { 'backgroundColor' : '#fffaff' },
                'xaxis' : { 'ticks' : active_devs_data['people'] }
            }
        )

        karma_data = self.karma()
        best_karma = TurboFlot([
            {
                'data' : karma_data['best'],
                'bars' : { 'show' : True }
            }],
            {
                'grid'  : { 'backgroundColor' : '#fffaff' },
                'xaxis' : { 'ticks' : karma_data['bestpkgs'] }
            }
        )
        return dict(security=security, all=all, most_updates=most_updates,
                    active_devs=active_devs, best_karma=best_karma)

    def cache_valid(self, graph):
        """
        Return whether or not our metrics cache is valid.  We're currently 
        storing cached metric values for 1 week.
        """
        if self.cache.has_key(graph):
            age = datetime.utcnow() - self.cache[graph][1]
            return age.days < 7

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
                if num < 20: # Trim off incomplete months
                    del timeline[release][month]
                    if months.has_key(month):
                        del months[month]
            timeline[release] = timeline[release].items()
        self.cache['security'] = [dict(timeline=timeline, months=months.items()),
                                  datetime.utcnow()]
        return self.cache['security'][0]

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
            if num < 300: # trim off incomplete months
                del all[month]
                del months[month]
                for type, data in timeline.items():
                    for m, n in data:
                        if m == month:
                            timeline[type].remove((m, n))
        self.cache['all'] = [dict(timeline=timeline, months=months.items(),
                                  all=all.items()), datetime.utcnow()]
        return self.cache['all'][0]

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

    def karma(self):
        """
            Return updates with the best and worst karma
        """
        if self.cache_valid('karma'):
            return self.cache['karma'][0]
        data = {} # { pkg : karma }
        for pkg in Package.select():
            data[pkg.name] = 0
            for update in pkg.updates():
                data[pkg.name] += update.karma
        items = data.items()
        items.sort(key=lambda x: x[1], reverse=True)
        bestitems = items[:10]
        worstitems = items[-10:]
        del data, items
        bestpkgs = {}
        bestdata = []
        worstpkgs = {}
        worstdata = []
        for i, item in enumerate(bestitems):
            bestpkgs[i + 0.5] = item[0]
            bestdata.append((i, item[1]))
        for i, item in enumerate(worstitems):
            worstpkgs[i + 0.5] = item[0]
            worstdata.append((i, item[1]))
        del worstitems, bestitems
        self.cache['karma'] = [dict(best=bestdata,
                                    bestpkgs=bestpkgs.items(),
                                    worst=worstdata,
                                    worstpkgs=worstpkgs.items()),
                               datetime.utcnow()]
        return self.cache['karma'][0]
