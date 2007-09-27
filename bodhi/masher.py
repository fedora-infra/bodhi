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

import os
import time
import logging
import commands

from bodhi import buildsys, mail
from bodhi.util import synchronized
from threading import Thread, Lock
from turbogears import config
from os.path import exists, join, islink

log = logging.getLogger(__name__)
masher = None
lock = Lock()

def get_masher():
    global masher
    return masher

class Masher:
    """
    The Masher.  This is a TurboGears extension that runs alongside bodhi that
    is in charge of queueing and dispatching mash composes.
    """
    def __init__(self):
        log.info("Starting the Masher")
        self._queue = []
        self._threads = []
        self.thread_id = 0
        self.mashing = 0
        self.last_log = None

    @synchronized(lock)
    def queue(self, updates, repos=set()):
        self._queue.append((self.thread_id, updates, repos))
        self.thread_id += 1
        if len(self._threads) == 0:
            if len(self._queue):
                self._mash(self._queue.pop())

    @synchronized(lock)
    def done(self, thread):
        """
        Called by each MashTask upon completion.  If there are more in the
        queue, then dispatch them.
        """
        log.info("MashTask %d done!" % thread.id)
        self.mashing = 0
        self.last_log = thread.log
        mail.send_releng('Bodhi Masher Report %s' % 
                         time.strftime("%y%m%d.%H%M"), thread.report())
        self._threads.remove(thread)
        if len(self._threads) == 0:
            if len(self._queue):
                self._mash(self._queue.pop())

    def _mash(self, task):
        """ Dispatch a given MashTask """
        thread = MashTask(task[0], task[1], task[2])
        self._threads.append(thread)
        thread.start()
        self.mashing = 1

    def lastlog(self):
        """
        Return the most recent mash (log_filename, log_data)
        """
        log = 'Previous mash log not available'
        if self.last_log and exists(self.last_log):
            logfile = file(self.last_log, 'r')
            log = logfile.read()
            logfile.close()
        return (self.last_log, log)

    def mash_tags(self, tags):
        """
        Run mash on a list of tags
        """
        self.queue([], tags)

    def __str__(self):
        """
        Return a string representation of the Masher, including the current
        queue and updates that are getting moved/mashed
        """
        val = 'Currently Mashing: %s\n\n' % (self.mashing and 'Yes' or 'No')
        if self.mashing:
            for thread in self._threads:
                val += str(thread)
            if len(self._queue):
                val += "\n[ Queue ]\n"
                for item in self._queue:
                    if len(item[1]):
                        val += "  Move tags\n"
                        for update in item[1]:
                            val += "  - %s (%s)" % (update.title,
                                                    update.request)
                    if len(item[2]):
                        val += "  Mash repos\n"
                        for repo in item[2]:
                            val += "  - %s" % repo

        (status, output) = commands.getstatusoutput("ps -U %d --forest v" %
                                                    os.getuid())
        val += "\n" + output

        return val


class MashTask(Thread):

    def __init__(self, id, updates, repos=set()):
        Thread.__init__(self)
        log.debug("MashTask(%d, %s)" % (id, updates))
        self.id = id
        self.tag = None
        self.updates = updates
        self.koji = buildsys.get_session()
        # which repos do we want to compose? (updates|updates-testing)
        self.repos = repos
        self.success = False
        self.cmd = 'mash -o %s -c ' + config.get('mash_conf') + ' -f %s '
        self.actions = [] # [(title, current_tag, new_tag), ...]
        self.mashing = False # are we currently mashing?
        self.moving = False # are we currently moving build tags?
        self.log = None # filename that we wrote mash output to
        self.mashed_repos = {} # { repo: mashed_dir }
        self.error_messages = []

    def safe_to_move(self):
        """
        Check for bodhi/koji inconsistencies, and make sure it is safe to
        perform actions against this set of updates
        """
        pending_nvrs = [build['nvr'] for build in
                        self.koji.listTagged('dist-fc7-updates-candidate')]
        testing_nvrs = [build['nvr'] for build in
                        self.koji.listTagged('dist-fc7-updates-testing')]
        stable_nvrs = [build['nvr'] for build in
                       self.koji.listTagged('dist-fc7-updates')]

        errors = False
        def error_log(msg):
            log.error(msg)
            self.error_messages.append(msg)
            errors = True

        for update in self.updates:
            for build in update.builds:
                if update.request == 'testing':
                    if build.nvr not in pending_nvrs:
                        error_log("%s not tagged as candidate" % build.nvr)
                elif update.request == 'stable':
                    if update.status == 'testing':
                        if build.nvr not in testing_nvrs:
                            error_log("%s not tagged as testing" % build.nvr)
                    elif update.status == 'pending':
                        if build.nvr not in pending_nvrs:
                            error_log("%s not tagged as candidate" % build.nvr)
                elif update.request == 'unpush':
                    if update.status == 'testing':
                        if build.nvr not in testing_nvrs:
                            error_log("%s not tagged as testing" % build.nvr)
                    elif update.status == 'stable':
                        if build.nvr not in stable_nvrs:
                            error_log("%s not tagged as stable" % build.nvr)
                else:
                    error_log("Unknown request '%s' for %s" % (update.request,
                                                               update.title))
        return errors

    def move_builds(self):
        """
        Move all builds associated with our batch of updates to the proper tag.
        This is determined based on the request of the update, and it's
        current state.
        """
        tasks = []
        success = False
        self.moving = True
        for update in self.updates:
            release = update.release.name.lower()
            if update.request == 'stable':
                self.repos.add('%s-updates' % release)
                self.repos.add('%s-updates-testing' % release)
                self.tag = update.release.dist_tag + '-updates'
            elif update.request == 'testing':
                self.repos.add('%s-updates-testing' % release)
                self.tag = update.release.dist_tag + '-updates-testing'
            elif update.request == 'obsolete':
                self.tag = update.release.dist_tag + '-updates-candidate'
                if update.status == 'testing':
                    self.repos.add('%s-updates-testing' % release)
                elif update.status == 'stable':
                    self.repos.add('%s-updates' % release)
            current_tag = update.get_build_tag()
            log.debug("Moving %s from %s to %s" % (update.title, current_tag,
                                                   self.tag))
            for build in update.builds:
                task_id = self.koji.moveBuild(current_tag, self.tag,
                                              build.nvr, force=True)
                self.actions.append((build.nvr, current_tag, self.tag))
                tasks.append(task_id)
        if buildsys.wait_for_tasks(tasks) == 0:
            success = True
        self.moving = False
        return success

    def undo_move(self):
        """
        Move the builds back to their original tag
        """
        log.debug("Rolling back updates to their original tag")
        tasks = []
        for action in self.actions:
            log.debug("Moving %s from %s to %s" % (action[0], action[2],
                                                   action[1]))
            task_id = self.koji.moveBuild(action[2], action[1], action[0],
                                          force=True)
            tasks.append(task_id)
        buildsys.wait_for_tasks(tasks)

    def update_comps(self):
        """
        Update our comps module, so we can pass it to mash to stuff into 
        our repositories
        """
        log.debug("Updating comps...")
        olddir = os.getcwd()
        os.chdir(config.get('comps_dir'))
        (status, output) = commands.getstatusoutput("cvs update")
        log.debug("(%d, %s) from cvs update" % (status, output))
        (status, output) = commands.getstatusoutput("make")
        log.debug("(%d, %s) from make" % (status, output))
        os.chdir(olddir)

    def update_symlinks(self):
        mashed_dir = config.get('mashed_dir')
        for repo, mashdir in self.mashed_repos.items():
            link = join(mashed_dir, repo)
            newrepo = join(mashdir, repo)
            log.debug("Running some sanity checks on %s" % newrepo)
            arches = os.listdir(newrepo)

            # make sure the new repository has our arches
            for arch in ('i386', 'x86_64', 'ppc'):
                if arch not in arches:
                    msg = "Cannot find arch %s in %s" % (arch, newrepo)
                    log.error(msg)
                    self.error_messages.append(msg)

            # make sure that mash didn't symlink our packages
            for pkg in os.listdir(join(newrepo, 'i386')):
                if pkg.endswith('.rpm'):
                    if islink(join(newrepo, 'i386', pkg)):
                        msg = "Mashed repository full of symlinks!"
                        log.error(msg)
                        self.error_messages.append(msg)
                        return
                    break

            if islink(link):
                os.unlink(link)
            os.symlink(newrepo, link)
            log.debug("Created symlink: %s => %s" % (newrepo, link))

    def mash(self):
        self.mashing = True
        self.update_comps()
        for repo in self.repos:
            mashdir = join(config.get('mashed_dir'), repo + '-' + \
                           time.strftime("%y%m%d.%H%M"))
            self.mashed_repos[repo] = mashdir
            comps = join(config.get('comps_dir'), 'comps-%s.xml' %
                         repo.split('-')[0])
            mashcmd = self.cmd % (mashdir, comps) + repo
            log.info("Running `%s`" % mashcmd)
            (status, output) = commands.getstatusoutput(mashcmd)
            log.info("status = %s" % status)
            if status == 0:
                self.success = True
                mash_output = '%s/mash.out' % mashdir
                out = file(mash_output, 'w')
                out.write(output)
                out.close()
                log.info("Wrote mash output to %s" % mash_output)
                self.log = mash_output
            else:
                self.success = False
                failed_output = join(config.get('mashed_dir'), 'mash-failed-%s'
                                     % time.strftime("%y%m%d.%H%M"))
                out = file(failed_output, 'w')
                out.write(output)
                out.close()
                log.info("Wrote failed mash output to %s" % failed_output)
                self.log = failed_output
                break
        self.mashing = False
        log.info("Mashing complete")

    def run(self):
        """
        Move all of the builds to the appropriate tag, and then run mash.  If
        anything fails, undo any tag moves.
        """
        try:
            if not self.safe_to_move():
                log.error("safe_to_move failed! -- aborting")
                masher.done(self)
                return
            t0 = time.time()
            if self.move_builds():
                log.debug("Moved builds in %s seconds" % (time.time() - t0))
                self.success = True
                t0 = time.time()
                self.mash()
                log.debug("Mashed for %s seconds" % (time.time() - t0))
                if self.success:
                    log.debug("Running post-request actions on updates")
                    for update in self.updates:
                        update.request_complete()
                    log.debug("Requests complete!")
                    self.generate_updateinfo()
                    self.update_symlinks()
                else:
                    log.error("Error mashing.. skipping post-request actions")
                    if self.undo_move():
                        log.info("Tag rollback successful!")
                    else:
                        log.error("Tag rollback failed!")
            else:
                log.error("Error with build moves.. rolling back")
                self.undo_move()
                self.success = False
        except Exception, e:
            log.error("Exception thrown in MashTask %d" % self.id)
            log.exception(str(e))
        masher.done(self)

    def generate_updateinfo(self):
        """
        Generate the updateinfo.xml.gz and insert it into the appropriate
        repositories.
        """
        from bodhi.metadata import ExtendedMetadata
        t0 = time.time()
        for repo, mashdir in self.mashed_repos.items():
            repo = join(mashdir, repo)
            log.debug("Generating updateinfo.xml.gz for %s" % repo)
            uinfo = ExtendedMetadata(repo)
            uinfo.insert_updateinfo()
        log.debug("Updateinfo generation took: %s secs" % (time.time()-t0))

    def __str__(self):
        val = '[ Mash Task #%d ]\n' % self.id
        if self.moving:
            val += '  Moving Updates\n'
            for action in self.actions:
                val += '   %s :: %s => %s\n' % (action[0], action[1], action[2])
        elif self.mashing:
            val += '  Mashing Repos %s\n' % ([str(repo) for repo in self.repos])
            for update in self.updates:
                val += '   %s (%s)\n' % (update.title, update.request)
        else:
            val += '  Not doing anything?'
        return val

    def report(self):
        val = '[ Mash Task #%d ]\n' % self.id
        val += 'The following actions were %ssuccessful.' % (self.success and
                                                             [''] or 
                                                             ['*NOT* '])[0]
        if len(self.error_messages):
            val += '\n The following errors occured:\n'
            for error in self.error_messages:
                val += error + '\n'
        if len(self.actions):
            val += '\n  Moved the following package tags:\n'
            for action in self.actions:
                val += '   %s :: %s => %s\n' % (action[0], action[1], action[2])
        if len(self.repos):
            val += '\n  Mashed the following repositories:\n'
            for repo in self.repos:
                val += '  - %s\n' % repo
        if self.log:
            mashlog = file(self.log, 'r')
            val += '\nMash Output:\n\n%s' % mashlog.read()
            mashlog.close()
        return val

def start_extension():
    global masher
    masher = Masher()

def shutdown_extension():
    log.info("Stopping Masher")
    global masher
    del masher
