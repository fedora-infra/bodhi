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
import datetime

from os.path import isdir, realpath, dirname, join, islink
from turbogears import scheduler, config

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
    for release in [rel.name.lower() for rel in Release.select()]:
        for repo in [release + '-updates', release + '-updates-testing']:
            liverepos.append(dirname(realpath(join(repos, repo))))
    for repo in [join(repos, repo) for repo in os.listdir(repos)]:
        if not islink(repo) and isdir(repo):
            fullpath = realpath(repo)
            if fullpath not in liverepos:
                log.info("Removing %s" % fullpath)
                #shutil.rmtree(fullpath)

def nagmail():
    # Nag submitters when their update has been sitting in testing for more
    # than two weeks.
    for update in PackageUpdate.select(PackageUpdate.q.status == 'testing'):
        if get_age_in_days(update.date_pushed) > 14:
            log.info("Nagging %s about testing update %s" % (update.submitter,
                     update.title))
            mail.send(update.submitter, 'old_testing', update)

    # Nag submitters if their update has been sitting unsubmitted in a pending
    # state for longer than a week.
    # TODO: implement this once the current 'pending' situation is under
    # control.  Right now, with our production instance, unpushed updates go
    # back into this state -- and we don't want to nag about those.

def schedule():
    """ Schedule our periodic tasks """

    # Weekly repository cleanup
    scheduler.add_interval_task(action=clean_repo,
                                taskname='Repository Cleanup',
                                initialdelay=0,
                                interval=604800)

    # Weekly nagmail
    scheduler.add_interval_task(action=nagmail,
                                taskname='Nagmail',
                                initialdelay=604800,
                                interval=604800)
