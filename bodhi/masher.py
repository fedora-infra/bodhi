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
#
# Authors: Luke Macken <lmacken@redhat.com>

import glob
import os
import sha
import time
import shutil
import urllib2
import logging
import subprocess
import cPickle as pickle
#import fedmsg

from collections import defaultdict
from operator import attrgetter
from sqlobject import SQLObjectNotFound, AND
from threading import Thread, Lock
from turbogears import config, url
from os.path import exists, join, islink, isdir, basename
from time import sleep

from bodhi import buildsys, mail
from bodhi.util import synchronized, sanity_check_repodata, get_nvr, sorted_builds
from bodhi.util import sort_updates
from bodhi.model import PackageUpdate, Release
from bodhi.metadata import ExtendedMetadata
from bodhi.exceptions import MashTaskException

log = logging.getLogger(__name__)
lock = Lock()


def get_masher():
    global masher
    if not masher:
        log.error("Masher doesn't exist?")
    return masher


def get_mash_conf():
    conf = config.get('mash_conf')
    if exists(conf):
        return conf
    elif exists('/etc/bodhi/mash.conf'):
        return '/etc/bodhi/mash.conf'
    else:
        log.error("No mash configuration found!")
        return None


class Masher(object):
    """ The Masher.

    This is an extension that is in charge of queueing and dispatching update
    pushes.  This process entails tagging all of the builds appropriately in
    the buildsystem, mashing the repositories, generating the
    updateinfo.xml.gz, closing/modifying bugzillas, sending notifications to
    developers/testers, and generating/sending update notices to various
    mailing lists.
    """
    def __init__(self):
        log.info("Starting the Masher")
        self._queue = []
        self._threads = []
        self.thread_id = 0
        self.mashing = False
        self.last_log = None

    @synchronized(lock)
    def queue(self, updates, repos=None, resume=False):
        self._queue.append((self.thread_id, updates, repos, resume))
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
        self.mashing = False
        self.last_log = thread.log
        mail.send_releng('Bodhi Masher Report %s' %
                         time.strftime("%y%m%d.%H%M"), thread.report())
        if thread in self._threads:
            self._threads.remove(thread)
        del thread
        if len(self._threads) == 0:
            if len(self._queue):
                self._mash(self._queue.pop())

    def _mash(self, task):
        """ Dispatch a given MashTask """
        thread = MashTask(task[0], task[1], task[2], task[3])
        self._threads.append(thread)
        thread.start()
        self.mashing = True

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
        val = 'Currently Mashing: %s\n\n' % self.mashing
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

        p = subprocess.Popen("ps -U %d --forest v" % os.getuid(), shell=True,
                             stdout=subprocess.PIPE)
        out, err = p.communicate()
        val += "\n" + out

        return val


class MashTask(Thread):

    def __init__(self, id, updates, repos=None, resume=False):
        """ Initialize a new MashTask thread.

        @param updates: a list of PackageUpdate objects that we want to push
        @param repos: a list of repositories to compose updates{,-testing)
        @param resume: resume this set of updates based on the assumption that
        we have already tagged them appropriately, and that all we need to do
        is mash the repositories, close bugs, and send out update notices.
        """
        Thread.__init__(self)
        repos = repos and set(repos) or set()
        log.debug("MashTask(%d, [%d updates], %s, %s)" % (id, len(updates), repos, resume))
        self.id = id
        self.tag = None
        self.updates = set()
        if updates and isinstance(updates[0], basestring):
            updates = map(PackageUpdate.byTitle, updates)

        for update in updates:
            if update.status == 'obsolete':
                log.warning("Skipping obsolete update %s" % update.title)
                continue
            if not update.request:
                log.warning('Skipping update without request: %s' % update.title)
                continue
            self.updates.add(update)
            if not resume:
                update.comment('This update is currently being pushed to the %s %s updates repository.' % (update.release.long_name, update.request), author='bodhi', email=False)

        if self.updates:
            up = self.updates.pop()
            self.updates.add(up)
            # eg: MASHING-FEDORA, MASHING-FEDORA-EPEL
            self.mash_lock_id = up.release.id_prefix
        else:
            self.mash_lock_id = 'UNKNOWN'
        self.koji = buildsys.get_session()
        # which repos do we want to compose? (updates|updates-testing)
        self.repos = repos
        self.success = False
        self.cmd = 'mash -o %s -c ' + config.get('mash_conf') + ' -f %s '
        self.actions = []  # [(title, current_tag, new_tag), ...]
        self.mashing = False  # are we currently mashing?
        self.moving = False  # are we currently moving build tags?
        self.log = None  # filename that we wrote mash output to
        self.mashed_repos = {}  # { repo: mashed_dir }
        self.errors = []
        self.safe = True
        self.genmd = False
        self.resume = resume
        self.testing_digest = {}
        self.composed_repos = []  # previously mashed repos from our MASHING lock
        self._lock()
        self._find_repos()

    def _lock(self):
        """ Write out what updates we are pushing and any successfully mashed
        repositories to our MASHING lock """
        mashed_dir = config.get('mashed_dir')
        mash_stage = config.get('mashed_stage_dir')
        mash_lock = join(mashed_dir, 'MASHING-%s' % self.mash_lock_id)
        if not os.path.isdir(mashed_dir):
            log.info("Creating mashed_dir %s" % mashed_dir)
            os.makedirs(mashed_dir)
        if not os.path.isdir(mash_stage):
            log.info("Creating mashed_stage_dir %s" % mash_stage)
            os.makedirs(mash_stage)
        if os.path.exists(mash_lock):
            if self.resume:
                log.debug("Resuming previous push!")
                lock = file(mash_lock, 'r')
                masher_state = pickle.load(lock)
                lock.close()

                # For backwards compatability, we need to make sure we handle
                # masher state that is just a list of updates, as well as a
                # dictionary of updates and successfully mashed repos
                if isinstance(masher_state, list):
                    for up in masher_state:
                        try:
                            up = PackageUpdate.byTitle(up)
                            self.updates.add(up)
                        except SQLObjectNotFound:
                            log.warning("Cannot find %s" % up)

                # { 'updates' : [PackageUpdate.title,],
                #   'repos'   : ['/path_to_completed_repo',] }
                elif isinstance(masher_state, dict):
                    for up in masher_state['updates']:
                        try:
                            up = PackageUpdate.byTitle(up)
                            self.updates.add(up)
                        except SQLObjectNotFound:
                            log.warning("Cannot find %s" % up)
                    for repo in masher_state['composed_repos']:
                        self.composed_repos.append(repo)
                else:
                    log.error('Unknown masher lock format: %s' % masher_state)
                    raise MashTaskException
            else:
                log.error("Previous mash not complete!  Either resume the last "
                          "push, or remove %s" % mash_lock)
                raise MashTaskException
        else:
            if self.resume:
                msg = "Trying to resume a push, yet %s doesn't exist!" % mash_lock
                log.error(msg)
                raise MashTaskException(msg)

            log.debug("Creating lock for updates push: %s" % mash_lock)
            lock = file(mash_lock, 'w')
            pickle.dump({
                'updates': [update.title for update in self.updates],
                'composed_repos': self.composed_repos,
            }, lock)
            lock.close()

    def _unlock(self):
        mash_lock = join(config.get('mashed_dir'), 'MASHING-%s' %
                         self.mash_lock_id)
        if os.path.exists(mash_lock):
            os.unlink(mash_lock)
        else:
            log.error("Cannot find MashTask lock at %s" % mash_lock)

    def _update_lock(self):
        """
        Update our masher state lockfile with any completed repos that we were
        able to compose during this push
        """
        log.debug("Updating MASHING-%s lock" % self.mash_lock_id)
        mash_lock = join(config.get('mashed_dir'), 'MASHING-%s' %
                         self.mash_lock_id)
        lock = file(mash_lock, 'r')
        masher_state = pickle.load(lock)
        lock.close()
        masher_state['composed_repos'] = self.composed_repos
        lock = file(mash_lock, 'w')
        pickle.dump(masher_state, lock)
        lock.close()

    def error_log(self, msg):
        log.error(msg)
        self.errors.append(msg)
        self.safe = False
        self.success = False

    def safe_to_move(self):
        """
        Check for bodhi/koji inconsistencies, and make sure it is safe to
        perform actions against this set of updates
        """
        pending_nvrs = {}
        testing_nvrs = {}
        stable_nvrs = {}
        log.debug("Making sure builds are safe to move")

        # For each release, populate the lists of pending/testing/stable builds
        for update in self.updates:
            if not update.release.name in pending_nvrs:
                pending_nvrs[update.release.name] = [
                    build['nvr'] for build in
                    self.koji.listTagged(update.release.candidate_tag)]
                testing_nvrs[update.release.name] = [
                    build['nvr'] for build in
                    self.koji.listTagged(update.release.testing_tag)]
                stable_nvrs[update.release.name] = [
                    build['nvr'] for build in
                    self.koji.listTagged(update.release.stable_tag)]

        for update in self.updates:
            for build in update.builds:
                if update.request == 'testing':
                    if update.status == 'testing':
                        if build.nvr not in testing_nvrs[update.release.name]:
                            self.error_log("%s not tagged as testing" %
                                           build.nvr)
                    elif update.status == 'pending':
                        if build.nvr not in pending_nvrs[update.release.name]:
                            self.error_log("%s not tagged as candidate" %
                                           build.nvr)
                elif update.request == 'stable':
                    if update.status == 'testing':
                        if build.nvr not in testing_nvrs[update.release.name]:
                            self.error_log("%s not tagged as testing" %
                                           build.nvr)
                    elif update.status == 'pending':
                        if build.nvr not in pending_nvrs[update.release.name]:
                            self.error_log("%s not tagged as candidate" %
                                           build.nvr)
                elif update.request == 'unpush':
                    if update.status == 'testing':
                        if build.nvr not in testing_nvrs[update.release.name]:
                            self.error_log("%s not tagged as testing" %
                                           build.nvr)
                    elif update.status == 'stable':
                        if build.nvr not in stable_nvrs[update.release.name]:
                            self.error_log("%s not tagged as stable" %
                                           build.nvr)
                elif update.request == 'obsolete':
                    if update.status == 'testing':
                        if build.nvr not in testing_nvrs[update.release.name]:
                            self.error_log("%s not tagged as testing" %
                                           build.nvr)
                    elif update.status == 'stable':
                        if build.nvr not in stable_nvrs[update.release.name]:
                            self.error_log("%s not tagged as stable" %
                                           build.nvr)
                else:
                    self.error_log("Unknown request '%s' for %s" % (
                                   update.request, update.title))

        del pending_nvrs, testing_nvrs, stable_nvrs
        return self.safe

    def safe_to_resume(self):
        """
        Check for bodhi/koji inconsistencies, and make sure it is safe to
        perform actions against this set of updates
        """
        testing_nvrs = {}
        stable_nvrs = {}
        log.debug("Making sure builds are safe to resume")

        # For each release, populate the lists of pending/testing/stable builds
        for update in self.updates:
            if not update.release.name in testing_nvrs:
                testing_nvrs[update.release.name] = [
                    build['nvr'] for build in
                    self.koji.listTagged(update.release.testing_tag)]
                stable_nvrs[update.release.name] = [
                    build['nvr'] for build in
                    self.koji.listTagged(update.release.stable_tag)]

        for update in self.updates:
            for build in update.builds:
                if update.request == 'testing':
                    if build.nvr not in testing_nvrs[update.release.name]:
                        self.error_log("%s not tagged as testing" % build.nvr)
                elif update.request == 'stable':
                    if build.nvr not in stable_nvrs[update.release.name]:
                        self.error_log("%s not tagged as stable" % build.nvr)

        return self.safe

    def _find_repos(self):
        """
        Based on our updates, build a list of repositories that we need to
        mash during this push
        """
        for update in self.updates:
            release = update.release

            # [No Frozen Rawhide] Don't mash stable repos for pending releases
            if update.request == 'stable' and release.locked:
                continue

            if self.resume:
                if not release.locked:
                    self.repos.add(release.stable_repo)
                self.repos.add(release.testing_repo)
            elif update.request == 'stable':
                self.repos.add(release.stable_repo)
                if update.status == 'testing':
                    self.repos.add(release.testing_repo)
            elif update.request == 'testing':
                self.repos.add(release.testing_repo)
            elif update.request == 'obsolete':
                if update.status == 'testing':
                    self.repos.add(release.testing_repo)
                elif update.status == 'stable':
                    self.repos.add(release.stable_repo)

    def move_builds(self):
        """
        Move all builds associated with our batch of updates to the proper tag.
        This is determined based on the request of the update, and it's
        current state.
        """
        t0 = time.time()
        self.success = False
        self.moving = True
        log.debug("Setting up koji multicall for moving builds")
        self.koji.multicall = True
        for update in sort_updates(self.updates):
            if update.request == 'stable':
                self.tag = update.release.stable_tag
                # [No Frozen Rawhide] Move stable builds going to a pending
                # release to the Release.dist-tag
                if update.release.locked:
                    self.tag = update.release.dist_tag
            elif update.request == 'testing':
                self.tag = update.release.testing_tag
            elif update.request == 'obsolete':
                self.tag = update.release.candidate_tag
            current_tag = update.get_build_tag()
            for build in update.builds:
                if build.inherited:
                    log.debug("Adding tag %s to %s" % (self.tag, build.nvr))
                    self.koji.tagBuild(self.tag, build.nvr, force=True)
                elif update.release.locked and update.request == 'stable':
                    log.debug("Adding tag %s to %s" % (self.tag, build.nvr))
                    self.koji.tagBuild(self.tag, build.nvr, force=True)
                else:
                    log.debug("Moving %s from %s to %s" % (build.nvr,
                                                           current_tag,
                                                           self.tag))
                    self.koji.moveBuild(current_tag, self.tag, build.nvr, force=True)
                self.actions.append((build.nvr, current_tag, self.tag))

        results = self.koji.multiCall()
        if not buildsys.wait_for_tasks([task[0] for task in results]):
            self.success = True
        self.moving = False
        log.debug("Moved builds in %s seconds" % (time.time() - t0))
        if not self.success:
            raise MashTaskException("Failed to move builds")

    def remove_pending_tags(self):
        """ Remove all pending tags from these updates """
        log.debug("Removing pending tags from builds")
        self.koji.multicall = True
        for update in self.updates:
            if update.request == 'stable':
                update.remove_tag(update.release.pending_stable_tag, koji=self.koji)
            elif update.request == 'testing':
                update.remove_tag(update.release.pending_testing_tag, koji=self.koji)
        self.koji.multiCall()

    def expire_buildroot_overrides(self):
        """ Obsolete any buildroot overrides that are in this push """
        for update in self.updates:
            if update.request == 'stable':
                try:
                    update.expire_buildroot_overrides()
                except Exception, e:
                    log.exception(e)

    # With a large pushes, this tends to cause much buildsystem churn, as well
    # as polluting the tag history.
    #def undo_move(self):
    #    """
    #    Move the builds back to their original tag
    #    """
    #    log.debug("Rolling back updates to their original tag")
    #    tasks = []
    #    for action in self.actions:
    #        log.debug("Moving %s from %s to %s" % (action[0], action[2],
    #                                               action[1]))
    #        task_id = self.koji.moveBuild(action[2], action[1], action[0],
    #                                      force=True)
    #        tasks.append(task_id)
    #    buildsys.wait_for_tasks(tasks)

    def update_comps(self):
        """
        Update our comps module, so we can pass it to mash to stuff into
        our repositories
        """
        log.debug("Updating comps...")
        comps_dir = config.get('comps_dir')
        comps_url = config.get('comps_url')
        if not exists(comps_dir):
            if comps_url.startswith('git://'):
                cmd = 'git clone %s' % (comps_url,)
            else:
                cmd = 'cvs -d %s co comps' % (comps_url,)
            log.debug("running command: %s" % cmd)
            subprocess.call(cmd, shell=True, cwd=comps_dir)
        if comps_url.startswith('git://'):
            log.debug('Running git pull')
            p = subprocess.Popen('git pull', shell=True, cwd=comps_dir,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            log.debug(out)
            if err:
                log.error(err)
        else:
            subprocess.call('cvs update', shell=True, cwd=comps_dir)

        log.info('Merging translations')
        p = subprocess.Popen('make', shell=True, cwd=comps_dir,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        log.debug(out)
        if err:
            log.error(err)

    def update_symlinks(self):
        """ Stage our updates repository.

        This entail doing various sanity checking, such as:
            - make sure each repo contains all supported arches
            - make sure we didn't compose a repo full of symlinks
            - sanity check our repodata

        If the above tests pass, then bodhi moves the repository to the
        mashed_stage_dir, and updates the live symlinks appropriately.
        """
        mashed_dir = config.get('mashed_dir')
        for repo, mashdir in self.mashed_repos.items():
            link = join(mashed_dir, repo)
            newrepo = join(mashdir, repo)
            arches = os.listdir(newrepo)

            log.debug("Running sanity checks on %s" % newrepo)

            # make sure the new repository has our arches
            for arch in config.get('arches').split():
                if '/' in arch:  # 'ppc/ppc64'
                    one, other = arch.split('/')
                    if one not in arches and other not in arches:
                        self.error_log("Cannot find arch %s OR %s in %s" % (one, other, newrepo))
                        raise MashTaskException
                    else:
                        if one in arches:
                            arch = one
                        else:
                            arch = other
                elif arch not in arches:
                    self.error_log("Cannot find arch %s in %s" % (arch, newrepo))
                    raise MashTaskException

                # sanity check our repodata
                try:
                    sanity_check_repodata(join(newrepo, arch, 'repodata'))
                except Exception, e:
                    self.error_log("Repodata sanity check failed!\n%s" % str(e))
                    raise MashTaskException

            # make sure that mash didn't symlink our packages
            for pkg in os.listdir(join(newrepo, arches[0])):
                if pkg.endswith('.rpm'):
                    if islink(join(newrepo, arches[0], pkg)):
                        self.error_log("Mashed repository full of symlinks!")
                        raise MashTaskException
                    break

            # move the new repo to our mash stage
            stage_dir = config.get('mashed_stage_dir')
            if mashed_dir != stage_dir:
                log.debug("Moving %s => %s" % (mashdir, stage_dir))
                shutil.move(mashdir, stage_dir)
            else:
                log.debug("mashed_dir and mashed_stage_dir are the same.")

            # create a mashed_stage_dir/repo symlink so it goes live
            if islink(link):
                os.unlink(link)
            os.symlink(newrepo, link)
            log.debug("Created symlink: %s => %s" % (newrepo, link))

    def cache_repodata(self):
        """
        Cache repodata for the repositories that we just mashed, so we can
        regenerate the updateinfo.xml with it later, along with letting
        createrepo '--update' our fresh repositories.
        """
        log.debug("Caching latest repodata")
        mashed_dir = config.get('mashed_dir')
        for repo, mashdir in self.mashed_repos.items():
            rdcache = join(mashed_dir, '%s.repodata' % repo)
            if isdir(rdcache):
                log.debug("Removing old repodata cache")
                shutil.rmtree(rdcache)
            os.makedirs(rdcache)
            for arch in os.listdir(join(mashdir, repo)):
                shutil.copytree(join(mashdir, repo, arch, 'repodata'),
                                join(rdcache, arch))

    def mash(self):
        t0 = time.time()
        self.mashing = True
        self.update_comps()
        # {'f9-updates': '/mnt/koji/mash/updates/f9-updates-080905.0057',}
        finished_repos = dict([('-'.join(basename(repo).split('-')[:-1]), repo)
                               for repo in self.composed_repos])
        for repo in self.repos:
            # Skip mashing this repo if we successfully mashed it previously
            if repo in finished_repos:
                log.info('Skipping previously mashed repo %s' % repo)
                self.mashed_repos[repo] = finished_repos[repo]
                continue

            #fedmsg.publish(topic="mashtask.mashing", msg=dict(repo=repo))

            mashdir = join(config.get('mashed_dir'), repo + '-' +
                           time.strftime("%y%m%d.%H%M"))
            self.mashed_repos[repo] = mashdir
            comps = join(config.get('comps_dir'), 'comps-%s.xml' %
                         repo.split('-')[0])
            updatepath = join(config.get('mashed_dir'), repo)
            mashcmd = self.cmd % (mashdir, comps) + '-p %s ' % updatepath + repo
            log.info("Running `%s`" % mashcmd)
            p = subprocess.Popen(mashcmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, shell=True)
            stdout, stderr = p.communicate()
            log.info("mash returncode = %s" % p.returncode)
            if p.returncode:
                self.success = False
                failed_output = join(config.get('mashed_dir'), 'mash-failed-%s'
                                     % time.strftime("%y%m%d.%H%M"))
                out = file(failed_output, 'w')
                out.write(stdout)
                if stderr:
                    out.write('\n\nstderr:\n\n')
                    out.write(stderr)
                out.close()
                log.info("Wrote failed mash output to %s" % failed_output)
                self.log = failed_output
                raise MashTaskException("Mash failed")
            else:
                self.success = True
                mash_output = '%s/mash.out' % mashdir
                out = file(mash_output, 'w')
                out.write(stdout)
                out.close()
                log.info("Wrote mash output to %s" % mash_output)
                self.log = mash_output
                self.composed_repos.append(mashdir)
                self._update_lock()
        self.mashing = False
        log.debug("Mashed for %s seconds" % (time.time() - t0))

    def run(self):
        """
        Move all of the builds to the appropriate tag, and then run mash.  If
        anything fails, undo any tag moves.
        """

        #fedmsg.publish(topic="mashtask.start", msg=dict())
        self.success = True
        try:
            if self.resume:
                if not self.safe_to_resume():
                    log.error("safe_to_resume failed! -- aborting")
                    masher.done(self)
                    return
            else:
                if not self.safe_to_move():
                    log.error("safe_to_move failed! -- aborting")
                    self._unlock()
                    masher.done(self)
                    return

            log.debug("Builds look OK to me")

            # Update all bug titles for security updates
            if not self.resume:
                log.info('Updating bug titles for security updates')
                for update in self.updates:
                    if update.type == 'security':
                        for bug in update.bugs:
                            bug.fetch_details()

            # Move koji build tags
            if not self.resume and len(self.updates):
                self.move_builds()
                self.expire_buildroot_overrides()

            # Remove all pending tags
            # TODO: Once AutoQA is Good To Go, then we'll want to prevent
            # updates from being pushed if they have not gotten the appropriate
            # karma from AutoQA.  For now, bodhi is simply handling the pending tags.
            if not self.resume:
                self.remove_pending_tags()

            # Mash our repositories
            self.mash()

            # Change the state of the updates, and generate the updates-testing
            # notification digest as well.
            log.debug("Running post-request actions on updates")
            for update in self.updates:
                if self.resume:
                    if update.request:
                        if update.request == 'testing':
                            update.request_complete()
                            self.add_to_digest(update)
                        else:
                            update.request_complete()
                    else:  # request_complete() has already been run on update
                        if update.status == 'testing':
                            self.add_to_digest(update)
                else:
                    if update.request == 'testing':
                        update.request_complete()
                        self.add_to_digest(update)
                    else:
                        update.request_complete()
            log.debug("Requests complete!")

            # Generate the updateinfo.xml for our repositories
            self.generate_updateinfo()

            # Run some sanity checks and flip the bits live
            self.update_symlinks()

            # Cache the latest repodata for later use
            self.cache_repodata()

            # Poll our master mirror and block until our updates hit
            #fedmsg.publish(topic="mashtask.sync.waiting", msg=dict())
            self.wait_for_sync()
            #fedmsg.publish(topic="mashtask.sync.complete", msg=dict())

            # Send out our notices/digest, update all bugs, and add comments
            log.debug("Sending stable update notices and closing bugs")
            for update in self.updates:
                try:
                    update.modify_bugs()
                except Exception, e:
                    log.error("There was a problem modifying the bugs for %s" % update.title)
                    log.exception(e)
                try:
                    update.status_comment()
                except Exception, e:
                    log.error("There was a problem updating the comment for %s" % update.title)
                    log.exception(e)
                if update.status == 'stable':
                    try:
                        update.send_update_notice()
                    except Exception, e:
                        log.error("There was a problem sending the notice for %s" % update.title)
                        log.exception(e)

            log.debug("Sending updates-testing digests")
            self.send_digest_mail()

        except Exception, e:
            log.error("Exception thrown in MashTask %d" % self.id)
            self.error_log(str(e))
            log.exception(str(e))
        except MashTaskException, e:
            log.error("MashTaskException thrown! %s" % str(e))
            self.success = False

        if self.success:
            log.debug("Success! Unlocking repo")
            self._unlock()
        else:
            # Update our masher state lockfile with any completed
            # repos that we were able to compose during this push
            log.debug("Mash unsuccessful, updating state lock")
            self._update_lock()

        #fedmsg.publish(topic="mashtask.complete", msg=dict(
        #    success=self.success,
        #))

        log.debug("MashTask done")
        masher.done(self)

    def add_to_digest(self, update):
        """
        Add an package to the digest dictionary
        { 'release-id':
          { 'build nvr' : body text for build, ...... }
        ..
        ..
        }
        """
        prefix = update.release.long_name
        if not prefix in self.testing_digest:
            self.testing_digest[prefix] = {}
        for i, subbody in enumerate(mail.get_template(
                update, use_template='maillist_template')):
            self.testing_digest[prefix][update.builds[i].nvr] = subbody[1]

    def get_unapproved_critpath_updates(self, release):
        release = Release.select(Release.q.long_name == release)[0]
        updates = []
        for update in PackageUpdate.select(
                AND(PackageUpdate.q.releaseID == release.id,
                    PackageUpdate.q.status == 'testing',
                    PackageUpdate.q.request == None),
                orderBy=PackageUpdate.q.date_submitted).reversed():
            if update.critpath and not update.critpath_approved:
                updates.append(update)
        updates = self.sort_by_days_in_testing(updates)
        return updates

    def get_security_updates(self, release):
        release = Release.select(Release.q.long_name == release)[0]
        updates = PackageUpdate.select(
            AND(PackageUpdate.q.releaseID == release.id,
                PackageUpdate.q.type == 'security',
                PackageUpdate.q.status == 'testing',
                PackageUpdate.q.request == None))
        updates = self.sort_by_days_in_testing(updates)
        return updates

    def sort_by_days_in_testing(self, updates):
        updates = list(updates)
        updates.sort(key=lambda update: update.days_in_testing, reverse=True)
        return updates

    def send_digest_mail(self):
        '''
        Send digest mail to mailing lists
        '''
        for prefix, content in self.testing_digest.items():
            log.debug("Sending digest for updates-testing %s" % prefix)
            maildata = u''
            try:
                security_updates = self.get_security_updates(prefix)
                if security_updates:
                    maildata += u'The following %s Security updates need testing:\n Age  URL\n' % prefix
                    for update in security_updates:
                        maildata += u' %3i  %s%s\n' % (update.days_in_testing, config.get('base_address'), url(update.get_url()))
                    maildata += '\n\n'

                critpath_updates = self.get_unapproved_critpath_updates(prefix)
                if critpath_updates:
                    maildata += u'The following %s Critical Path updates have yet to be approved:\n Age URL\n' % prefix
                    for update in self.get_unapproved_critpath_updates(prefix):
                        maildata += u' %3i  %s%s\n' % (update.days_in_testing, config.get('base_address'), url(update.get_url()))
                    maildata += '\n\n'
            except Exception, e:
                log.exception(e)

            maildata += u'The following builds have been pushed to %s updates-testing\n\n' % prefix
            # get a list af all nvr's
            updlist = content.keys()
            # sort the list
            updlist.sort()
            # Add the list of builds to the mail
            for pkg in updlist:
                maildata += u'    %s\n' % pkg
            # Add some space between the short list and the Details"
            maildata += u'\nDetails about builds:\n\n'
            # Add the detail of each build
            for nvr in updlist:
                maildata += u"\n" + self.testing_digest[prefix][nvr]
            release = Release.select(Release.q.long_name == prefix)[0]
            mail.send_mail(config.get('bodhi_email'),
                           config.get('%s_test_announce_list' %
                                      release.id_prefix.lower()
                                             .replace('-', '_')),
                           '%s updates-testing report' % prefix,
                           maildata)

    def wait_for_sync(self):
        """
        Block until our repomd.xml hits the master mirror
        """
        if not len(self.updates):
            log.debug("No updates in masher; skipping wait_for_sync")
            return
        log.info("Waiting for updates to hit mirror...")
        update = self.updates.pop()
        release = update.release
        self.updates.add(update)
        mashdir = config.get('mashed_dir')
        repo = release.stable_repo
        master_repomd = config.get('%s_master_repomd' %
                                   release.id_prefix.lower().replace('-', '_'))
        repomd = join(mashdir, repo, 'i386', 'repodata', 'repomd.xml')
        if not exists(repomd):
            log.error("Cannot find local repomd: %s" % repomd)
            return
        checksum = sha.new(file(repomd).read()).hexdigest()
        while True:
            sleep(600)
            try:
                masterrepomd = urllib2.urlopen(master_repomd % release.get_version())
            except urllib2.URLError, e:
                log.error("Error fetching repomd.xml: %s" % str(e))
                continue
            except urllib2.HTTPError, e:
                log.error("Error fetching repomd.xml: %s" % str(e))
                continue
            newsum = sha.new(masterrepomd.read()).hexdigest()
            if newsum == checksum:
                log.debug("master repomd.xml matches!")
                return
            log.debug("master repomd.xml doesn't match! %s != %s" % (checksum,
                                                                     newsum))

    def generate_updateinfo(self):
        """
        Generate the updateinfo.xml.gz and insert it into the appropriate
        repositories.
        """
        self.genmd = True
        t0 = time.time()
        for repo, mashdir in self.mashed_repos.items():
            # File name is prefixed with a hash, use a glob to find it
            olduinfos = glob.glob(os.path.join(config.get('mashed_dir'),
                                               '%s.repodata' % repo, '*',
                                               "*updateinfo.xml.gz"))

            if len(olduinfos) >= 1:
                olduinfo = olduinfos[0]

            else:
                olduinfo = None

            repo = join(mashdir, repo)
            log.debug("Generating updateinfo.xml.gz for %s" % repo)
            uinfo = ExtendedMetadata(repo, olduinfo)
            uinfo.insert_updateinfo()
            uinfo.insert_pkgtags()

        log.debug("Updateinfo generation took: %s secs" % (time.time() - t0))
        self.genmd = False

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
        elif self.genmd:
            val += '  Generating extended update metadata'
        else:
            val += '  Not doing anything?'
        return val

    def report(self):
        val = '[ Mash Task #%d ]\n' % self.id
        val += 'The following actions were %ssuccessful.' % (self.success and
                                                             [''] or
                                                             ['*NOT* '])[0]
        if len(self.errors):
            val += '\n The following errors occured:\n'
            for error in self.errors:
                val += error + '\n'
        if len(self.actions):
            val += '\n  Moved the following package tags:\n'
            for action in self.actions:
                val += '   %s :: %s => %s\n' % (action[0], action[1], action[2])
        if len(self.repos):
            val += '\n  Mashed the following repositories:\n'
            for repo in self.repos:
                val += '  - %s\n' % repo
        if not self.success and self.log:
            mashlog = file(self.log, 'r')
            val += '\nMash Output:\n\n%s' % mashlog.read()
            mashlog.close()
        if len(self.errors):
            log.error(val)
        else:
            log.info(val)
        return val

masher = Masher()
