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
    def success(self, thread):
        log.debug("MashTask %d successful!" % thread.id)
        for update in thread.updates:
            log.debug("Doing post-request stuff for %s" % update.nvr)
            update.request_complete()

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
                         time.strftime("%y%m%d.%H%M"), "The following tasks " +
                         "were successful.\n\n" + thread.report())
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
                            val += "  - %s (%s)" % (update.nvr, update.request)
                    if len(item[2]):
                        val += "  Mash repos\n"
                        for repo in item[2]:
                            val += "  - %s" % repo
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
        self.cmd = 'mash -o %s -c ' + config.get('mash_conf') + ' '
        self.actions = [] # [(nvr, current_tag, new_tag), ...]
        self.mashing = False # are we currently mashing?
        self.moving = False # are we currently moving build tags?
        self.log = None # filename that we wrote mash output to

    def move_builds(self):
        tasks = []
        success = False
        self.moving = True
        for update in self.updates:
            release = update.release.name.lower()
            if update.request == 'move':
                self.repos.add('%s-updates' % release)
                self.repos.add('%s-updates-testing' % release)
                self.tag = update.release.dist_tag + '-updates'
            elif update.request == 'push':
                self.repos.add('%s-updates-testing' % release)
                self.tag = update.release.dist_tag + '-updates-testing'
            elif update.request == 'unpush':
                self.tag = update.release.dist_tag + '-updates-candidate'
                if update.status == 'testing':
                    self.repos.add('%s-updates-testing' % release)
                elif update.status == 'stable':
                    self.repos.add('%s-updates' % release)
            current_tag = update.get_build_tag()
            log.debug("Moving %s from %s to %s" % (update.nvr, current_tag,
                                                   self.tag))
            task_id = self.koji.moveBuild(current_tag, self.tag,
                                          update.nvr, force=True)
            self.actions.append((update.nvr, current_tag, self.tag))
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

    def mash(self):
        self.mashing = True
        for repo in self.repos:
            mashdir = join(config.get('mashed_dir'), repo + '-' + \
                           time.strftime("%y%m%d.%H%M"))
            mashcmd = self.cmd % mashdir
            log.info("Running mash on %s" % repo)
            (status, output) = commands.getstatusoutput(mashcmd + repo)
            log.info("status = %s" % status)
            if status == 0:
                self.success = True
                mash_output = '%s/mash.out' % mashdir
                out = file(mash_output, 'w')
                out.write(output)
                out.close()
                log.info("Wrote mash output to %s" % mash_output)
                self.log = mash_output

                # create a symlink to new repo
                link = join(config.get('mashed_dir'), repo)
                if islink(link):
                    os.unlink(link)
                os.symlink(join(mashdir, repo), link)
            else:
                failed_output = join(config.get('mashed_dir'), 'mash-failed-%s'
                                     % time.strftime("%y%m%d.%H%M"))
                out = file(failed_output, 'w')
                out.write(output)
                out.close()
                log.info("Wrote failed mash output to %s" % failed_output)
                self.log = failed_output
        self.mashing = False
        log.info("Mashing complete")

    def run(self):
        """
        Move all of the builds to the appropriate tag, and then run mash.  If
        anything fails, undo any tag moves.
        """
        if self.move_builds():
            self.mash()
            if self.success:
                masher.success(self)
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
        masher.done(self)

    def __str__(self):
        val = '[ Mash Task #%d ]\n' % self.id
        if self.moving:
            val += '  Moving Updates\n'
            for action in self.actions:
                val += '   %s :: %s => %s\n' % (action[0], action[1], action[2])
        elif self.mashing:
            val += '  Mashing Repos %s\n' % ([str(repo) for repo in self.repos])
            for update in self.updates:
                val += '   %s (%s)\n' % (update.nvr, update.request)
        else:
            val += '  Not doing anything?'
        return val

    def report(self):
        val = '[ Mash Task #%d ]' % self.id
        val += 'The following actions were %ssuccessful.' % (self.success and ''
                                                             or '*NOT* ')
        if len(self.actions):
            val += '\n  Moved the following package tags:'
            for action in self.actions:
                val += '   %s :: %s => %s\n' % (action[0], action[1], action[2])
        val += '  Mashed the following repositories:'
        for repo in self.repos:
            val += '  - %s' % repo
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
