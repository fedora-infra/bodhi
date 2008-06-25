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

"""
    This module is for functions that are to be executed on a regular basis
    using the TurboGears scheduler.
"""

import os
import shutil
import logging

from os.path import isdir, realpath, dirname, join, islink, exists
from datetime import datetime
from turbogears import scheduler, config
from sqlobject.sqlbuilder import AND

from bodhi import mail
from bodhi.util import get_age_in_days
from bodhi.model import Release, PackageUpdate

log = logging.getLogger(__name__)


def clean_repo():
    """
    Clean up our mashed_dir, removing all referenced repositories
    """
    log.info("Starting clean_repo job")
    liverepos = []
    repos = config.get('mashed_dir')
    if exists(join(repos, 'MASHING')):
        log.info("Mash in progress.  Aborting clean_repo job")
        return
    for release in [rel.name.lower() for rel in Release.select()]:
        # TODO: keep the 2 most recent repos!
        for repo in [release + '-updates', release + '-updates-testing']:
            liverepos.append(dirname(realpath(join(repos, repo))))
    for repo in [join(repos, repo) for repo in os.listdir(repos)]:
        if not islink(repo) and isdir(repo):
            fullpath = realpath(repo)
            if fullpath not in liverepos:
                log.info("Removing %s" % fullpath)
                shutil.rmtree(fullpath)
    log.info("clean_repo complete!")


def nagmail():
    """
    Nag the submitters of updates based on a list of queries
    """
    log.info("Starting nagmail job!")

    queries = [
            ('old_testing', PackageUpdate.select(
                                    AND(PackageUpdate.q.status == 'testing',
                                        PackageUpdate.q.request == None)),
             lambda update: update.date_pushed),
            ('old_pending', PackageUpdate.select(
                                    AND(PackageUpdate.q.status == 'pending',
                                        PackageUpdate.q.request == None)),
             lambda update: update.date_submitted),
    ]

    for name, query, date in queries:
        for update in query:
            if get_age_in_days(date(update)) > 14:
                if update.nagged:
                    if update.nagged.has_key(name) and update.nagged[name]:
                        x = (datetime.utcnow() - update.nagged[name]).days
                        if (datetime.utcnow() - update.nagged[name]).days < 7:
                            continue # Only nag once a week at most
                    nagged = update.nagged
                else:
                    nagged = {}
                log.info("[%s] Nagging %s about %s" % (name, update.submitter,
                                                       update.title))
                mail.send(update.submitter, name, update)
                nagged[name] = datetime.utcnow()
                update.nagged = nagged

    log.info("nagmail complete!")


def fix_bug_titles():
    """
    Go through all bugs with invalid titles and see if we can re-fetch them.
    If bugzilla is down, then bodhi simply replaces the title with
    'Unable to fetch bug title' or 'Invalid bug number'.  So lets occasionally
    see if we can re-fetch those bugs.
    """
    from bodhi.model import Bugzilla
    from sqlobject.sqlbuilder import OR
    log.debug("Running fix_bug_titles job")
    for bug in Bugzilla.select(
                 OR(Bugzilla.q.title == 'Invalid bug number',
                    Bugzilla.q.title == 'Unable to fetch bug title')):
        bug.fetch_details()


def cache_release_data():
    """Refresh some commonly used peices of information.

    This entails things like all releases, and how many updates exist for
    each type of update for each release.  These pieces of information are in
    the master template, and we want to avoid hitting the db multiple times
    for each visit (as much as possible).

    """
    from bodhi.model import Releases
    Releases().update()


def refresh_metrics():
    """ Refresh all of our graphs and metrics """
    log.info("Regenerating update metrics...")
    from bodhi.metrics import MetricData
    MetricData().refresh()
    log.info("Regeneration of metrics complete")


def schedule():
    """ Schedule our periodic tasks """

    # Weekly repository cleanup
    scheduler.add_interval_task(action=clean_repo,
                                taskname="Clean update repositories",
                                initialdelay=604800,
                                interval=604800)

    # Daily nagmail
    scheduler.add_weekday_task(action=nagmail,
                               weekdays=range(1,8),
                               timeonday=(0,0))

    # Fix invalid bug titles
    scheduler.add_interval_task(action=fix_bug_titles,
                                taskname='Fix bug titles',
                                initialdelay=1200,
                                interval=604800)

    # Warm up some data caches
    scheduler.add_interval_task(action=cache_release_data,
                                taskname='Cache release data',
                                initialdelay=0,
                                interval=3600)

    # If we're the masher, then handle the costly metric regenration
    if not config.get('masher'):
        scheduler.add_interval_task(action=refresh_metrics,
                                    taskname='Refresh our metrics',
                                    initialdelay=0,
                                    interval=172800)
