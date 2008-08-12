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
#
# Authors: Luke Macken <lmacken@redhat.com>

import logging
from datetime import datetime

from sqlobject import SQLObjectNotFound
from turboflot import TurboFlot
from turbogears import expose, config, flash, redirect
from turbogears.controllers import Controller

from bodhi.util import Singleton, get_age_in_days
from bodhi.model import PackageUpdate, Release, hub

log = logging.getLogger(__name__)


class Metric(object):

    def __init__(self, release):
        """ Initialize this metric for a given release """
        raise NotImplementedError

    def update(self, update):
        """ Process an update """
        raise NotImplementedError

    def done(self):
        """ Finish processing """
        raise NotImplementedError

    def get_data(self):
        """ Return a dictionary of metric specific data """
        raise NotImplementedError

    def get_widget(self):
        """ Return a TurboFlot widget for this metric """
        raise NotImplementedError


class AllMetric(Metric):
    """
    A metric of all stable updates, comparing the various types
    """
    def __init__(self, release):
        self.all = {}       # { month : num }
        self.months = {}    # { month_num : month_name }
        self.timeline = {}  # { type : { month : num } } 
        self.earliest = datetime.now()
        self.release = release
        for update_type in config.get('update_types').split():
            self.timeline[update_type] = {}

    def update(self, update):
        if update.status != 'stable':
            return
        if update.date_pushed < self.earliest:
            self.earliest = update.date_pushed
        if not self.timeline[update.type].has_key(update.date_pushed.month):
            self.timeline[update.type][update.date_pushed.month] = 0
            self.months[update.date_pushed.month] = \
                    update.date_pushed.strftime("%b")
        if not self.all.has_key(update.date_pushed.month):
            self.all[update.date_pushed.month] = 0
        for build in update.builds:
            self.timeline[update.type][update.date_pushed.month] += 1
            self.all[update.date_pushed.month] += 1

    def done(self):
        for update_type, data in self.timeline.items():
            self.timeline[update_type] = data.items()

        # Append earlier months for newer years to the end of the graph
        self.months = self.months.items()
        self.months.sort(key=lambda x: x[0])
        m = []
        for num, month in self.months:
            if num < self.earliest.month:
                m.append([num, month])
        for num, month in m:
            self.months.remove((num, month))
        for i, n in enumerate(m):
            newid = self.months[-1][0] + i + 1
            for amonth, anum in self.all.items():
                if amonth == m[i][0]:
                    del self.all[amonth]
                    self.all[newid] = anum
                    break
            for update_type in self.timeline:
                for tlmonth, tlnum in self.timeline[update_type]:
                    if tlmonth == m[i][0]:
                        self.timeline[update_type].remove((tlmonth, tlnum))
                        self.timeline[update_type].append((newid, tlnum))
            m[i][0] = newid
        self.months += m

    def get_widget(self, data):
        return TurboFlot([
            {
                'data'  : data['all'],
                'label' : 'All Updates',
                'bars'  : {'show': 'true'}
            },
            {
                'data'   : data['timeline']['enhancement'],
                'label'  : 'Enhancement',
                'lines'  : {'show': 'true'},
                'points' : {'show': 'true'}
            },
            {
                'data'   : data['timeline']['security'],
                'label'  : 'Security',
                'lines'  : {'show': 'true'},
                'points' : {'show': 'true'}
            },
            {
                'data'   : data['timeline']['bugfix'],
                'label'  : 'Bugfix',
                'lines'  : {'show': 'true'},
                'points' : {'show': 'true'}
            }],
            {
                'xaxis' : {'ticks': data['months']},
            },
            label = '%s Updates' % self.release.long_name
        )

    def get_data(self):
        return dict(timeline=self.timeline, months=self.months,
                    all=self.all.items())


class MostUpdatedMetric(Metric):
    """
    A metric that calculates what packages have been updated the most.
    """
    def __init__(self, release):
        self.release = release.long_name
        self.data = {}
        self.pkgs = []

    def update(self, update):
        for build in update.builds:
            if not self.data.has_key(build.package.name):
                self.data[build.package.name] = 0
            self.data[build.package.name] += 1

    def done(self):
        items = self.data.items()
        items.sort(key=lambda x: x[1], reverse=True)
        items = items[:7]
        del self.data
        self.data = {}
        for i, item in enumerate(items):
            self.data[i] = item[1]
            self.pkgs.append((i + 0.5, item[0]))

    def get_data(self):
        return dict(packages=self.data.items(), pkgs=self.pkgs)

    def get_widget(self, data):
        return TurboFlot([
            # Hack, to get the color we want :)
            {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
            {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
            {
                'data': data['packages'],
                'bars': {'show': 'true'}
            }],
            {
                'xaxis': {'ticks': data['pkgs']}
            },
            label = 'Most Updated Packages in %s' % self.release.long_name
        )


class ActiveDevsMetric(Metric):
    """
    A metric that calculates which developers have pushed out the most updates
    """
    def __init__(self, release):
        self.release = release.long_name
        self.users = {} # { user : # updates }
        self.data = {}

    def update(self, update):
        if not self.users.has_key(update.submitter):
            self.users[update.submitter] = 0
        self.users[update.submitter] += 1

    def done(self):
        items = self.users.items()
        items.sort(key=lambda x: x[1], reverse=True)
        items = items[:10]
        del self.users
        self.users = []
        for i, item in enumerate(items):
            self.data[i + 0.5] = item[0]
            self.users.append((i, item[1]))

    def get_data(self):
        return dict(data=self.users, people=self.data.items())

    def get_widget(self, data):
        return TurboFlot([
            {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
            {
                'data': data['data'],
                'bars': {'show': 'true'}
            }],
            {
                'xaxis': {'ticks': data['people']}
            },
            label = 'Most updates per developer in %s' % self.release.long_name
        )


class KarmaMetric(Metric):
    """
    A metric that calculates packages that have received the best and worst
    feedback.
    """
    def __init__(self, release):
        self.data = {} # { pkg : karma }
        self.release = release.long_name
        self.bestpkgs = {}
        self.bestdata = []
        self.worstpkgs = {}
        self.worstdata = []

    def update(self, update):
        for build in update.builds:
            if not self.data.has_key(build.package.name):
                self.data[build.package.name] = 0
            self.data[build.package.name] += update.karma

    def done(self):
        items = self.data.items()
        items.sort(key=lambda x: x[1], reverse=True)
        for i, item in enumerate(items[:8]):
            self.bestpkgs[i + 0.5] = item[0]
            self.bestdata.append((i, item[1]))
        for i, item in enumerate(items[-8:]):
            self.worstpkgs[i + 0.5] = item[0]
            self.worstdata.append((i, item[1]))
        del items, self.data

    def get_data(self):
        return dict(best=self.bestdata, bestpkgs=self.bestpkgs.items(),
                    worst=self.worstdata, worstpkgs=self.worstpkgs.items())

    def get_widget(self, data):
        return TurboFlot([
            {
                'data': data['best'],
                'bars': {'show': True}
            }],
            {
                'xaxis': {'ticks': data['bestpkgs']}
            },
            label = 'Packages with best karma'
        )


class TopTestersMetric(Metric):
    """
    A metric that calculates the people that have provided the most 
    testing feedback for updates
    """
    def __init__(self, release):
        self.release = release.long_name
        self.data = {}   # { person : # of comments }
        self.people = {}

    def update(self, update):
        for comment in update.comments:
            if comment.author == 'bodhi' or comment.karma == 0:
                continue
            if not self.data.has_key(comment.author):
                self.data[comment.author] = 0
            self.data[comment.author] += 1

    def done(self):
        items = self.data.items()
        items.sort(key=lambda x: x[1], reverse=True)
        items = items[:8]
        self.data = []
        for i, item in enumerate(items):
            self.people[i + 0.5] = item[0]
            self.data.append((i, item[1]))

    def get_data(self):
        return dict(people=self.people.items(), data=self.data)

    def get_widget(self, data):
        return TurboFlot([
            {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
            {'data': [[0,0]]}, {'data': [[0,0]]},
            {'data': [[0,0]]}, {'data': [[0,0]]},
            {
                'data': data['data'],
                'bars': {'show': True}
            }],
            {
                'xaxis': {'ticks': data['people']}
            },
            label = 'Top %s testers' % self.release.long_name
        )


class MostTestedMetric(Metric):
    """
    A metric that calculates the packages with the most +1/-1 comments
    """
    def __init__(self, release):
        self.release = release.long_name
        self.data = {} # {pkg: # of +1/-1's}
        self.tested_data = []
        self.tested_pkgs = {}

    def update(self, update):
        for build in update.builds:
            if not self.data.has_key(build.package.name):
                self.data[build.package.name] = 0
            for comment in update.comments:
                if comment.karma in (1, -1):
                    self.data[build.package.name] += 1

    def done(self):
        items = self.data.items()
        items.sort(key=lambda x: x[1], reverse=True)
        for i, item in enumerate(items[:8]):
            self.tested_pkgs[i + 0.5] = item[0]
            self.tested_data.append((i, item[1]))

    def get_data(self):
        return dict(data=self.tested_data, pkgs=self.tested_pkgs.items())

    def get_widget(self, data):
        return TurboFlot([
            {'data': [[0,0]]}, {'data': [[0,0]]}, {'data': [[0,0]]},
            {'data': [[0,0]]}, {'data': [[0,0]]},
            {
                'data': data['data'],
                'bars': {'show': True}
            }],
            {
                'xaxis': {'ticks': data['pkgs']}
            },
            label = 'Most tested %s packages' % self.release
        )


class UpdateTypeMetric(Metric):
    """
    This metric calculates the number of updates of various types for all
    releases.  This data is used by the sidebar in our master template.  It is
    generated by the masher, cached in the Release.metrics column, which is
    then cached by our frontends every day.
    """
    def __init__(self, release):
        self.release = {
            'id': release.id,
            'name': release.name,
            'long_name': release.long_name,
            'num_pending': 0,
            'num_testing': 0,
            'num_stable': 0,
            'num_obsolete': 0,
            'num_security': 0,
            'num_bugfix': 0,
            'num_enhancement': 0,
            'num_newpackage': 0,
        }

    def update(self, update):
        self.release['num_%s' % update.status] += 1
        if update.pushed:
            self.release['num_%s' % update.type] += 1

    def done(self):
        pass

    def get_data(self):
        return self.release

    def get_widget(self, data):
        pass


##
## All of the metrics that we are going to generate
##
metrics = [AllMetric, MostUpdatedMetric, ActiveDevsMetric, KarmaMetric,
           TopTestersMetric, MostTestedMetric, UpdateTypeMetric,]


class MetricData(Singleton):

    widgets = {} # { release : { type : TurboFlot } }
    metrics = []
    age = None

    def get_widgets(self, release):
        """ Return the metrics for a specified release.

        If our metric widgets are more than a day old, recreate them with
        fresh metrics from our database.
        """
        if self.age and get_age_in_days(self.age) < 1:
            return self.widgets[release]

        log.debug("Generating some fresh metric widgets...")
        freshwidgets = {}
        for rel in Release.select():
            if not rel.metrics:
                log.warning("No metrics found for %s" % rel.name)
                return
            #self.init_metrics(rel) # Really?
            if not freshwidgets.has_key(rel.name):
                freshwidgets[rel.name] = {}
            for metric in self.metrics:
                widget = metric.get_widget(rel.metrics[metric.__class__.__name__])
                if widget:
                    freshwidgets[rel.name][metric.__class__.__name__] = widget

        self.widgets = freshwidgets 
        self.age = datetime.utcnow()
        return self.widgets[release]

    def init_metrics(self, release):
        """ Initialize our Metric objects for a given release """
        self.metrics = []
        for metric in metrics:
            self.metrics.append(metric(release))

    def refresh(self):
        """ Refresh all of the metrics for all releases.

        For each release, initialize our metrics objects, and feed them every
        update for that release.  Do the necessary calculations, and then save
        our metrics to the database in the Release.metrics PickleCol.
        """
        log.info("Doing a hard refresh of our metrics data")
        metrics = {}
        updates = {} # {release: [updates,]}
        all_updates = list(PackageUpdate.select())
        releases = list(Release.select())
        for release in releases:
            updates[release.name] = []
        for update in all_updates:
            updates[update.release.name].append(update)
        for release in releases:
            log.debug("Calculating metrics for %s" % release.name)
            self.init_metrics(release)
            for update in updates[release.name]:
                for metric in self.metrics:
                    metric.update(update)
            for metric in self.metrics:
                metric.done()
                metrics[metric.__class__.__name__] = metric.get_data()
            release.metrics = metrics
        hub.commit()
        del all_updates
        del releases
        log.info("Metrics generation complete!")


class MetricsController(Controller):

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
        widgets = MetricData().get_widgets(release)
        if not widgets:
            return dict(metrics=[], title="Metrics currently unavailable")
        return dict(metrics=[widgets[name.__name__] for name in metrics
                             if name.__name__ in widgets],
                    title="%s Update Metrics" % rel.long_name)
