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

from sqlobject import SQLObjectNotFound
from turboflot import TurboFlot
from turbogears import expose, config, flash, redirect
from turbogears.controllers import Controller

from bodhi.util import Singleton
from bodhi.model import PackageUpdate, Release

metrics = ('all', 'most_updated', 'top_testers', 'active_devs', 'karma',
           'most_tested')


class MetricData(Singleton):

    widgets = {} # { release : { type : TurboFlot } }

    def get_data(self, release):
        """ Return the metrics for a specified release """
        return self.widgets[release]

    def refresh(self):

        for release in Release.select():

            # Start all of our co-routines
            coroutines = [getattr(self, metric)() for metric in metrics]
            for coroutine in coroutines:
                coroutine.next()

            # Feed our co-routines updates
            for update in PackageUpdate.select(
                    PackageUpdate.q.releaseID == release.id):
                for coroutine in coroutines:
                    coroutine.send(update)

            # Close our co-routines
            for coroutine in coroutines:
                coroutine.close()

            if not self.widgets.has_key(release.name):
                self.widgets[release.name] = {}

            # Create our TurboFlot widgets with our new data
            self.widgets[release.name]['all'] = TurboFlot([
                {
                    'data'  : self.all_data['all'],
                    'label' : 'All Updates',
                    'bars'  : {'show': 'true'}
                },
                {
                    'data'   : self.all_data['timeline']['enhancement'],
                    'label'  : 'Enhancement',
                    'lines'  : {'show': 'true'},
                    'points' : {'show': 'true'}
                },
                {
                    'data'   : self.all_data['timeline']['security'],
                    'label'  : 'Security',
                    'lines'  : {'show': 'true'},
                    'points' : {'show': 'true'}
                },
                {
                    'data'   : self.all_data['timeline']['bugfix'],
                    'label'  : 'Bugfix',
                    'lines'  : {'show': 'true'},
                    'points' : {'show': 'true'}
                }],
                {
                    'xaxis' : {'ticks': self.all_data['months']},
                },
                label = '%s Updates' % release.long_name
            )

            self.widgets[release.name]['most_updated'] = TurboFlot([
                # Hack to get the color we want :)
                {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
                {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
                {
                    'data': self.most_data['packages'],
                    'bars': {'show': 'true'}
                }],
                {
                    'xaxis': {'ticks': self.most_data['pkgs']}
                },
                label = 'Most Updated Packages'
            )

            self.widgets[release.name]['active_devs'] = TurboFlot([
                {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
                {
                    'data': self.active_devs_data['data'],
                    'bars': {'show': 'true'}
                }],
                {
                    'xaxis': {'ticks': self.active_devs_data['people']}
                },
                label = 'Most updates per developer'
            )

            self.widgets[release.name]['karma'] = TurboFlot([
                {
                    'data': self.karma_data['best'],
                    'bars': {'show': True}
                }],
                {
                    'xaxis': {'ticks': self.karma_data['bestpkgs']}
                },
                label = 'Packages with best karma'
            )

            self.widgets[release.name]['top_testers'] = TurboFlot([
                {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
                {'data': [[0,0]]}, {'data': [[0,0]]},
                {'data': [[0,0]]}, {'data': [[0,0]]},
                {
                    'data': self.tester_data['data'],
                    'bars': {'show': True}
                }],
                {
                    'xaxis': {'ticks': self.tester_data['people']}
                },
                label = 'Top testers'
            )

            self.widgets[release.name]['most_tested'] = TurboFlot([
                {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
                {'data': [[0,0]]}, {'data': [[0,0]]},
                {
                    'data': self.most_tested_data['data'],
                    'bars': {'show': True}
                }],
                {
                    'xaxis': {'ticks': self.most_tested_data['pkgs']}
                },
                label = 'Most tested packages'
            )

    def all(self):
        """ A co-routine to generate metrics for the supplied updates """
        timeline = {} # { type : { month : num } } 
        for update_type in config.get('update_types').split():
            timeline[update_type] = {}

        months = {} # { month_num : month_name }
        all = {} # { month : num }
        starting_month = 6
        earliest = datetime.now()
        try:
            while True:
                update = (yield)
                if update.status != 'stable':
                    continue
                if update.date_pushed < earliest:
                    earliest = update.date_pushed
                if not timeline[update.type].has_key(update.date_pushed.month):
                    timeline[update.type][update.date_pushed.month] = 0
                    months[update.date_pushed.month] = \
                            update.date_pushed.strftime("%b")
                if not all.has_key(update.date_pushed.month):
                    all[update.date_pushed.month] = 0
                for build in update.builds:
                    timeline[update.type][update.date_pushed.month] += 1
                    all[update.date_pushed.month] += 1
        except GeneratorExit:
            for update_type, data in timeline.items():
                timeline[update_type] = data.items()

            # Append earlier months for newer years to the end of the graph
            months = months.items()
            months.sort(key=lambda x: x[0])
            m = []
            for num, month in months:
                if num < earliest.month:
                    m.append([num, month])
            for num, month in m:
                months.remove((num, month))
            for i, n in enumerate(m):
                newid = months[-1][0] + i + 1
                for amonth, anum in all.items():
                    if amonth == m[i][0]:
                        del all[amonth]
                        all[newid] = anum
                        break
                for update_type in timeline:
                    for tlmonth, tlnum in timeline[update_type]:
                        if tlmonth == m[i][0]:
                            timeline[update_type].remove((tlmonth, tlnum))
                            timeline[update_type].append((newid, tlnum))
                m[i][0] = newid
            months += m

            self.all_data = dict(timeline=timeline, months=months,
                                 all=all.items())

    def most_updated(self):
        """ Return update statistics by package for a given release """
        data = {}
        pkgs = []
        try:
            while True:
                update = (yield)
                for build in update.builds:
                    if not data.has_key(build.package.name):
                        data[build.package.name] = 0
                    data[build.package.name] += 1
        except GeneratorExit:
            items = data.items()
            items.sort(key=lambda x: x[1], reverse=True)
            items = items[:7]
            del data
            data = {}
            for i, item in enumerate(items):
                data[i] = item[1]
                pkgs.append((i + 0.5, item[0]))
            self.most_data = dict(packages=data.items(), pkgs=pkgs)

    def active_devs(self):
        """ Return update statistics by developer per release """
        users = {} # { user : # updates }
        data = {}
        try:
            while True:
                update = (yield)
                if not users.has_key(update.submitter):
                    users[update.submitter] = 0
                users[update.submitter] += 1
        except GeneratorExit:
            items = users.items()
            items.sort(key=lambda x: x[1], reverse=True)
            items = items[:10]
            del users
            users = []
            for i, item in enumerate(items):
                data[i + 0.5] = item[0]
                users.append((i, item[1]))
            self.active_devs_data = dict(data=users, people=data.items())

    def karma(self):
        """ Return updates with the best and worst karma for a given release """
        data = {} # { pkg : karma }
        try:
            while True:
                update = (yield)
                for build in update.builds:
                    if not data.has_key(build.package.name):
                        data[build.package.name] = 0
                    data[build.package.name] += update.karma
        except GeneratorExit:
            items = data.items()
            items.sort(key=lambda x: x[1], reverse=True)
            bestpkgs = {}
            bestdata = []
            worstpkgs = {}
            worstdata = []
            for i, item in enumerate(items[:8]):
                bestpkgs[i + 0.5] = item[0]
                bestdata.append((i, item[1]))
            for i, item in enumerate(items[-8:]):
                worstpkgs[i + 0.5] = item[0]
                worstdata.append((i, item[1]))
            del items, data
            self.karma_data = dict(best=bestdata, bestpkgs=bestpkgs.items(),
                                   worst=worstdata, worstpkgs=worstpkgs.items())

    def top_testers(self):
        data = {}   # { person : # of comments }
        people = {}
        try:
            while True:
                update = (yield)
                for comment in update.comments:
                    if comment.author == 'bodhi' or comment.karma == 0:
                        continue
                    if not data.has_key(comment.author):
                        data[comment.author] = 0
                    data[comment.author] += 1
        except GeneratorExit:
            items = data.items()
            items.sort(key=lambda x: x[1], reverse=True)
            items = items[:8]
            data = []
            for i, item in enumerate(items):
                people[i + 0.5] = item[0]
                data.append((i, item[1]))
            self.tester_data = dict(people=people.items(), data=data)

    def most_tested(self):
        data = {} # {pkg: # of +1/-1's}
        try:
            while True:
                update = (yield)
                for build in update.builds:
                    if not data.has_key(build.package.name):
                        data[build.package.name] = 0
                    for comment in update.comments:
                        if comment.karma in (1, -1):
                            data[build.package.name] += 1
        except GeneratorExit:
            items = data.items()
            items.sort(key=lambda x: x[1], reverse=True)
            tested_data = []
            tested_pkgs = {}
            for i, item in enumerate(items[:8]):
                tested_pkgs[i + 0.5] = item[0]
                tested_data.append((i, item[1]))
            self.most_tested_data = dict(data=tested_data,
                                         pkgs=tested_pkgs.items())


class Metrics(Controller):

    @expose(template='bodhi.templates.metrics')
    def index(self, release=None):
        try:
            if not release:
                rel = Release.select()[0]
                release = rel.name
            else:
                rel = Release.byName(release)
        except SQLObjectNotFound:
            flash("Unknown Release: %s" % release)
            raise redirect('/metrics')
        data = MetricData().get_data(release)
        return dict(metrics=[data[name] for name in metrics],
                    title="%s Update Metrics" % rel.long_name)
