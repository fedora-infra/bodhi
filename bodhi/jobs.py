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
import logging
import subprocess

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
    mash_locks = set()
    for release in Release.select():
        lock = join(repos, 'MASHING-%s' % release.id_prefix)
        mash_locks.add(lock)
        if exists(lock):
            log.info("Mash in progress.  Aborting clean_repo job")
            return
    for release in [rel.name.lower() for rel in Release.select()]:
        # TODO: keep the 2 most recent repos!
        for repo in [release + '-updates', release + '-updates-testing']:
            liverepos.append(dirname(realpath(join(repos, repo))))
    for repo in [join(repos, repo) for repo in os.listdir(repos)]:
        if 'repodata' in repo: # skip our repodata caches
            continue
        if not islink(repo) and isdir(repo):
            fullpath = realpath(repo)
            if fullpath not in liverepos:
                log.info("Removing %s" % fullpath)
                subprocess.call(['rm', '-fr', fullpath])

        # Bail out if a push started in the middle of this job
        for lock in mash_locks:
            if exists(lock):
                log.warning('Mash lock detected!  Stopping clean_repo job.')
                return

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
             lambda update: update.days_in_testing),
            ('old_pending', PackageUpdate.select(
                                    AND(PackageUpdate.q.status == 'pending',
                                        PackageUpdate.q.request == None)),
             lambda update: get_age_in_days(update.date_submitted)),
    ]
    oldname = None
    mail_admin = False
    #mail_proventesters = False

    for name, query, date in queries:
        for update in query:
            if date(update) > 14:
                if update.nagged:
                    if update.nagged.has_key(name) and update.nagged[name]:
                        if (datetime.utcnow() - update.nagged[name]).days < 7:
                            continue # Only nag once a week at most
                    nagged = update.nagged
                else:
                    nagged = {}

                if update.critpath:
                    if update.critpath_approved:
                        continue
                    else:
                        oldname = name
                        name = 'old_testing_critpath'
                        mail_admin = True
                        #mail_proventesters = True

                log.info("[%s] Nagging %s about %s" % (name, update.submitter,
                                                       update.title))
                mail.send(update.submitter, name, update)
                if mail_admin:
                    mail.send_admin(name, update)
                    mail_admin = False
                #if mail_proventesters:
                #    mail.send(config.get('proventesters_email'), name, update)
                #    mail_proventesters = False

                nagged[name] = datetime.utcnow()
                update.nagged = nagged

                if oldname:
                    name = oldname
                    oldname = None

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
    log.info("Caching release metrics")
    from bodhi.model import Releases
    try:
        Releases().update()
    except Exception, e:
        log.exception(e)
    log.info("Release cache complete")


def refresh_metrics():
    """ Refresh all of our graphs and metrics """
    from bodhi.metrics import MetricData
    try:
        MetricData().refresh()
    except Exception, e:
        log.exception(e)


def approve_testing_updates():
    """
    Scan all testing updates and approve ones that have met the per-release
    testing requirements.

    https://fedoraproject.org/wiki/Package_update_acceptance_criteria
    """
    log.info('Running approve_testing_updates job...')
    for update in PackageUpdate.select(
            AND(PackageUpdate.q.status == 'testing',
                PackageUpdate.q.request == None)):
        # If this release does not have any testing requirements, skip it
        if not update.release.mandatory_days_in_testing:
            continue
        # If this has already met testing requirements, skip it
        if update.met_testing_requirements:
            continue
        # If this is a critpath update, skip it, since they have their own
        # testing requirements, aside from spending time in testing.
        if update.critpath:
            continue
        if update.meets_testing_requirements:
            log.info('%s now meets testing requirements' % update.title)
            update.comment(
                config.get('testing_approval_msg') % update.days_in_testing,
                author='bodhi')
    log.info('approve_testing_updates job complete.')


def schedule():
    """ Schedule our periodic tasks """

    jobs = config.get('jobs')

    # Weekly repository cleanup
    if 'clean_repo' in jobs:
        log.debug("Scheduling clean_repo job")
        scheduler.add_interval_task(action=clean_repo,
                                    taskname="Clean update repositories",
                                    initialdelay=604800,
                                    interval=604800)

    # Daily nagmail
    if 'nagmail' in jobs:
        log.debug("Scheduling nagmail job")
        scheduler.add_weekday_task(action=nagmail,
                                   weekdays=range(1,8),
                                   timeonday=(0,0))

    # Fix invalid bug titles
    if 'fix_bug_titles' in jobs:
        log.debug("Scheduling fix_bug_titles job")
        scheduler.add_interval_task(action=fix_bug_titles,
                                    taskname='Fix bug titles',
                                    initialdelay=1200,
                                    interval=604800)

    # Warm up some data caches
    if 'cache_release_data' in jobs:
        log.debug("Scheduling cache_release_data job")
        scheduler.add_interval_task(action=cache_release_data,
                                    taskname='Cache release data',
                                    initialdelay=0,
                                    interval=43200)

    # If we're the masher, then handle the costly metric regenration
    if not config.get('masher') and 'refresh_metrics' in jobs:
        log.debug("Scheduling refresh_metrics job")
        scheduler.add_interval_task(action=refresh_metrics,
                                    taskname='Refresh our metrics',
                                    initialdelay=7200,
                                    interval=86400)

    # Approve updates that have been in testing for a certain amount of time
    if 'approve_testing_updates' in jobs:
        log.debug("Scheduling approve_testing_updates job")
        scheduler.add_interval_task(action=approve_testing_updates,
                                   # Run every 6 hours
                                   initialdelay=21600,
                                   interval=21600)
                                   #weekdays=range(1,8),
                                   #timeonday=(0,0))
