# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
The Bodhi "Masher".

This module is responsible for the process of "pushing" updates out. It's
comprised of a fedmsg consumer that launches threads for each repository being
mashed.
"""

import os
import json
import time
import urllib2
import hashlib
import threading
import fedmsg.consumers

from collections import defaultdict

from bodhi import log, buildsys, notifications, mail, util
from bodhi.util import sorted_updates, sanity_check_repodata
from bodhi.config import config
from bodhi.models import (Update, UpdateRequest, UpdateType, Release,
                          UpdateStatus, ReleaseState)
from bodhi.metadata import ExtendedMetadata


class Masher(fedmsg.consumers.FedmsgConsumer):
    """The Bodhi Masher.

    A fedmsg consumer that listens for messages from releng members.

    An updates "push" consists of::

    - Verify that the message was sent by someone in releng
    - Determine which updates to push
    - Lock repo
      - track which repos were completed
      - track which packages are in the push
      - lock updates
    - Make sure things are safe to move? (ideally we should trust our own state)
    - Check with taskotron to see if updates are pushable.
    - Update security bug titles
    - Move build tags
    - Expire buildroot overrides
    - Remove pending tags
    - Send fedmsgs
    - Update comps
    - mash

Things to do while we're waiting on mash
    - Add testing updates to updates-testing digest
    - Generate/update updateinfo.xml

Once mash is done:
    - inject the updateinfo it into the repodata
    - Sanity check the repo
    - Flip the symlinks to the new repo
    - Cache the new repodata

    - Generate and email stable update notices
    - Wait for the repo to hit the master mirror
    - Update bugzillas
    - Add comments to updates
    - Email updates-testing digest
    - request_complete

    - Unlock repo
        - unlock updates
        - see if any updates now meet the stable criteria, and set the request
    """
    config_key = 'masher'

    def __init__(self, hub, db_factory, mash_dir=config.get('mash_dir'),
                 *args, **kw):
        self.db_factory = db_factory
        self.mash_dir = mash_dir
        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = prefix + '.' + env + '.' + hub.config.get('masher_topic')
        self.valid_signer = hub.config.get('releng_fedmsg_certname')
        if not self.valid_signer:
            log.warn('No releng_fedmsg_certname defined'
                     'Cert validation disabled')
        super(Masher, self).__init__(hub, *args, **kw)
        log.info('Bodhi masher listening on topic: %s' % self.topic)

    def consume(self, msg):
        self.log.info(msg)
        if self.valid_signer:
            if not fedmsg.crypto.validate_signed_by(msg, self.valid_signer,
                                                    **self.hub.config):
                self.log.error('Received message with invalid signature!'
                               'Ignoring.')
                # TODO: send email notifications
                return
        with self.db_factory() as session:
            try:
                self.work(session, msg)
            except:
                log.exception('Problem in Masher.work')

    def prioritize_updates(self, releases):
        """Return 2 batches of repos: important, and normal.

        At the moment an important repo is one that contains a security update.
        """
        important, normal = [], []
        for release in releases:
            for request, updates in releases[release].items():
                for update in updates:
                    if update.type is UpdateType.security:
                        important.append((release, request, updates))
                        break
                else:
                    normal.append((release, request, updates))
        return important, normal

    def work(self, session, msg):
        """Begin the push process.

        Here we organize & prioritize the updates, and fire off seperate
        threads for each reop tag being mashed.

        If there are any security updates in the push, then those repositories
        will be executed before all others.
        """
        body = msg['body']['msg']
        resume = body.get('resume', False)
        notifications.publish(topic="mashtask.start", msg=dict())
        releases = self.organize_updates(session, body)

        # Important repos first, then normal
        for batch in self.prioritize_updates(releases):
            # Stable first, then testing
            for req in ('stable', 'testing'):
                threads = []
                for release, request, updates in batch:
                    if request == req:
                        updates = [update.title for update in updates]
                        log.debug('Starting thread for %s %s for %d updates',
                                  release, request, len(updates))
                        thread = MasherThread(release, request, updates,
                                              self.log, self.db_factory,
                                              self.mash_dir, resume)
                        threads.append(thread)
                        thread.start()
                for thread in threads:
                    thread.join()

        self.log.info('Push complete!')

    def organize_updates(self, session, body):
        # {Release: {UpdateRequest: [Update,]}}
        releases = defaultdict(lambda: defaultdict(list))
        for title in body['updates'].split():
            update = session.query(Update).filter_by(title=title).first()
            if update:
                repo = releases[update.release.name][update.request.value]
                repo.append(update)
            else:
                self.log.warn('Cannot find update: %s' % title)
        return releases


class MasherThread(threading.Thread):

    def __init__(self, release, request, updates, log, db_factory,
                 mash_dir, resume=False):
        super(MasherThread, self).__init__()
        self.db_factory = db_factory
        self.log = log
        self.mash_dir = mash_dir
        self.request = UpdateRequest.from_string(request)
        self.release = release
        self.resume = resume
        self.updates = set()
        self.add_tags = []
        self.move_tags = []
        self.testing_digest = {}
        self.state = {
            'tagged': False,
            'updates': updates,
            'completed_repos': []
        }

    def run(self):
        with self.db_factory() as session:
            self.db = session
            self.work()
            self.db = None

    def work(self):
        self.koji = buildsys.get_session()
        self.release = self.db.query(Release)\
                              .filter_by(name=self.release).one()
        self.id = getattr(self.release, '%s_tag' % self.request.value)
        self.log.info('Running MasherThread(%s)' % self.id)
        self.init_state()
        self.init_path()

        notifications.publish(topic="mashtask.mashing", msg=dict(
            repo=self.id,
            updates=self.state['updates'],
        ))

        success = False
        try:
            self.save_state()
            self.load_updates()

            if not self.resume:
                self.lock_updates()

            self.verify_updates()

            if self.request is UpdateRequest.stable:
                self.perform_gating()

            self.update_security_bugs()


            if not self.state.get('tagged', False):
                self.determine_tag_actions()
                self.perform_tag_actions()
                self.state['tagged'] = True
                self.save_state()

            self.expire_buildroot_overrides()
            self.remove_pending_tags()
            self.update_comps()

            mash_thread = self.mash()

            # Things we can do while we're mashing
            self.complete_requests()
            self.generate_testing_digest()
            uinfo = self.generate_updateinfo()

            self.wait_for_mash(mash_thread)

            uinfo.insert_updateinfo()
            uinfo.insert_pkgtags()
            uinfo.cache_repodata()

            self.sanity_check_repo()
            self.stage_repo()

            # Wait for the repo to hit the master mirror
            self.wait_for_sync()

            # Send fedmsg notifications
            self.send_notifications()

            # Update bugzillas
            self.modify_bugs()

            # Add comments to updates
            self.status_comments()

            # Announce stable updates to the mailing list
            self.send_stable_announcements()

            # Email updates-testing digest
            self.send_testing_digest()

            success = True
            self.remove_state()
            self.unlock_updates()
            self.check_karma_thresholds()
        except:
            self.log.exception('Exception in MasherThread(%s)' % self.id)
            self.save_state()
        finally:
            self.finish(success)

    def load_updates(self):
        self.log.debug('Loading updates')
        updates = []
        for title in self.state['updates']:
            update = self.db.query(Update).filter_by(title=title).first()
            if update:
                updates.append(update)
        if not updates:
            raise Exception('Unable to load updates: %r' %
                            self.state['updates'])
        self.updates = updates

    def lock_updates(self):
        self.log.debug('Locking updates')
        for update in self.updates:
            update.locked = True
        self.db.flush()

    def unlock_updates(self):
        self.log.debug('Unlocking updates')
        for update in self.updates:
            update.locked = False
        self.db.flush()

    def check_karma_thresholds(self):
        """
        If we just pushed testing updates see if any of them now meet either of
        the karma thresholds
        """
        if self.request is UpdateRequest.testing:
            log.info('Determing if any testing updates reached the karma '
                     'thresholds during the push')
            for update in self.updates:
                update.check_karma_thresholds(username=u'bodhi')

    def verify_updates(self):
        for update in list(self.updates):
            if update.request is not self.request:
                reason = "Request %s inconsistent with mash request %s" % (
                    update.request, self.request)
                self.eject_from_mash(update, reason)
                continue

            if update.release is not self.release:
                reason = "Release %s inconsistent with mash release %s" % (
                    update.release, self.release)
                self.eject_from_mash(update, reason)
                continue

    def perform_gating(self):
        self.log.debug('Performing gating.')
        for update in list(self.updates):
            result, reason = update.check_requirements(self.db, config)
            if not result:
                self.log.warn("%s failed gating: %s" % (update.title, reason))
                self.eject_from_mash(update, reason)

    def eject_from_mash(self, update, reason):
        update.locked = False
        text = '%s ejected from the push because %r' % (update.title, reason)
        update.comment(text, author='bodhi')
        update.request = None
        if update in self.state['updates']:
            self.state['updates'].remove(update)
        if update in self.updates:
            self.updates.remove(update)
        notifications.publish(topic="update.eject", msg=dict(
            repo=self.id,
            update=update,
            reason=reason,
            request=self.request,
            release=self.release,
        ))

    def init_path(self):
        self.path = os.path.join(self.mash_dir, self.id + '-' +
                                 time.strftime("%y%m%d.%H%M"))
        if not os.path.isdir(self.path):
            os.makedirs(self.path)

    def init_state(self):
        if not os.path.exists(self.mash_dir):
            self.log.info('Creating %s' % self.mash_dir)
            os.makedirs(self.mash_dir)
        self.mash_lock = os.path.join(self.mash_dir, 'MASHING-%s' % self.id)
        if os.path.exists(self.mash_lock) and not self.resume:
            self.log.error('Trying to do a fresh push and masher lock already '
                           'exists: %s' % self.mash_lock)
            raise Exception

    def save_state(self):
        """
        Save the state of this push so it can be resumed later if necessary
        """
        with file(self.mash_lock, 'w') as lock:
            json.dump(self.state, lock)
        self.log.info('Masher lock saved: %s', self.mash_lock)

    def remove_state(self):
        self.log.info('Removing state: %s', self.mash_lock)
        os.remove(self.mash_lock)

    def finish(self, success):
        self.log.info('Thread(%s) finished.  Success: %r' % (self.id, success))
        notifications.publish(topic="mashtask.complete", msg=dict(
            success=success, repo=self.id))

    def update_security_bugs(self):
        """Update the bug titles for security updates"""
        self.log.info('Updating bug titles for security updates')
        for update in self.updates:
            if update.type is UpdateType.security:
                for bug in update.bugs:
                    bug.update_details()

    def determine_tag_actions(self):
        tag_types, tag_rels = Release.get_tags()
        for update in sorted_updates(self.updates):
            if update.status is UpdateStatus.testing:
                status = 'testing'
            else:
                status = 'candidate'

            for build in update.builds:
                from_tag = None
                tags = build.get_tags()
                for tag in tags:
                    if tag in tag_types[status]:
                        from_tag = tag
                        break
                else:
                    self.log.error('Cannot find relevant tag for %s: %s' % (
                                   build.nvr, tags))
                    raise Exception

                if (self.release.state is ReleaseState.pending and
                        update.request is UpdateRequest.stable):
                    self.add_tags.append((update.requested_tag, build.nvr))
                else:
                    self.move_tags.append((from_tag, update.requested_tag,
                                           build.nvr))

    def perform_tag_actions(self):
        self.koji.multicall = True
        for action in self.add_tags:
            tag, build = action
            self.log.info("Adding tag %s to %s" % (tag, build))
            self.koji.tagBuild(tag, build, force=True)
        for action in self.move_tags:
            from_tag, to_tag, build = action
            self.log.info('Moving %s from %s to %s' % (
                          build, from_tag, to_tag))
            self.koji.moveBuild(from_tag, to_tag, build, force=True)
        results = self.koji.multiCall()
        failed_tasks = buildsys.wait_for_tasks([task[0] for task in results])
        if failed_tasks:
            raise Exception("Failed to move builds: %s" % failed_tasks)

    def expire_buildroot_overrides(self):
        """ Obsolete any buildroot overrides that are in this push """
        for update in self.updates:
            if update.request is UpdateRequest.stable:
                for build in update.builds:
                    if build.override:
                        build.override.expire()

    def remove_pending_tags(self):
        """ Remove all pending tags from these updates """
        self.log.debug("Removing pending tags from builds")
        self.koji.multicall = True
        for update in self.updates:
            if update.request is UpdateRequest.stable:
                update.remove_tag(update.release.pending_stable_tag,
                                  koji=self.koji)
            elif update.request is UpdateRequest.testing:
                update.remove_tag(update.release.pending_testing_tag,
                                  koji=self.koji)
        result = self.koji.multiCall()
        self.log.debug('remove_pending_tags koji.multiCall result = %r',
                       result)

    def update_comps(self):
        """
        Update our comps git module and merge the latest translations so we can
        pass it to mash insert into the repodata.
        """
        self.log.info("Updating comps")
        comps_dir = config.get('comps_dir')
        comps_url = config.get('comps_url')
        if not os.path.exists(comps_dir):
            util.cmd(['git', 'clone', comps_url], os.path.dirname(comps_dir))
        if comps_url.startswith('git://'):
            util.cmd(['git', 'pull'], comps_dir)
        else:
            self.log.error('comps_url must start with git://')
            return
        util.cmd(['make'], comps_dir)

    def mash(self):
        if self.path in self.state['completed_repos']:
            self.log.info('Skipping completed repo: %s', self.path)
            return

        comps = os.path.join(config.get('comps_dir'), 'comps-%s.xml' %
                             self.release.branch)
        previous = os.path.join(config.get('mash_stage_dir'), self.id)

        mash_thread = MashThread(self.id, self.path, comps, previous)
        mash_thread.start()
        return mash_thread

    def wait_for_mash(self, mash_thread):
        self.log.debug('Waiting for mash thread to finish')
        mash_thread.join()
        if mash_thread.success:
            self.state['completed_repos'].append(self.path)
            self.save_state()
        else:
            raise Exception

    def complete_requests(self):
        self.log.info("Running post-request actions on updates")
        for update in self.updates:
            if update.request:
                update.request_complete()
            else:
                self.log.warn('Update %s missing request', update.title)

    def add_to_digest(self, update):
        """Add an package to the digest dictionary.

        {'release-id': {'build nvr': body text for build, ...}}
        """
        prefix = update.release.long_name
        if prefix not in self.testing_digest:
            self.testing_digest[prefix] = {}
        for i, subbody in enumerate(mail.get_template(
                update, use_template='maillist_template')):
            self.testing_digest[prefix][update.builds[i].nvr] = subbody[1]

    def generate_testing_digest(self):
        self.log.info('Generating testing digest for %s' % self.release.name)
        for update in self.updates:
            if update.status is UpdateStatus.testing:
                self.add_to_digest(update)

    def generate_updateinfo(self):
        self.log.info('Generating updateinfo for %s' % self.release.name)
        uinfo = ExtendedMetadata(self.release, self.request,
                                 self.db, self.path)
        return uinfo

    def sanity_check_repo(self):
        """Sanity check our repo.

            - make sure each repo contains all supported arches
            - make sure we didn't compose a repo full of symlinks
            - sanity check our repodata
        """
        arches = os.listdir(self.path)
        self.log.debug("Running sanity checks on %s" % self.path)

        # make sure the new repository has our arches
        for arch in config.get('arches').split():
            if '/' in arch:  # 'ppc/ppc64'
                one, other = arch.split('/')
                if one not in arches and other not in arches:
                    self.log.error("Cannot find arch %s OR %s in %s" %
                                   (one, other, self.path))
                    raise Exception
                else:
                    if one in arches:
                        arch = one
                    else:
                        arch = other
            elif arch not in arches:
                self.log.error("Cannot find arch %s in %s" % (arch, self.path))
                raise Exception

            # sanity check our repodata
            try:
                repodata = os.path.join(self.path, arch, 'repodata')
                sanity_check_repodata(repodata)
            except Exception, e:
                self.log.error("Repodata sanity check failed!\n%s" % str(e))
                raise

        # make sure that mash didn't symlink our packages
        for pkg in os.listdir(os.path.join(self.path, arches[0])):
            if pkg.endswith('.rpm'):
                if os.path.islink(os.path.join(self.path, arches[0], pkg)):
                    self.log.error("Mashed repository full of symlinks!")
                    raise Exception
                break

        return True

    def stage_repo(self):
        """Symlink our updates repository into the staging directory"""
        stage_dir = config.get('mash_stage_dir')
        if not os.path.isdir(stage_dir):
            self.log.info('Creating mash_stage_dir %s', stage_dir)
            os.mkdir(stage_dir)
        link = os.path.join(stage_dir, self.id)
        if os.path.islink(link):
            os.unlink(link)
        self.log.info("Creating symlink: %s => %s" % (self.path, link))
        os.symlink(self.path, link)

    def wait_for_sync(self):
        """Block until our repomd.xml hits the master mirror"""
        self.log.info('Waiting for updates to hit the master mirror')
        notifications.publish(topic="mashtask.sync.wait", msg=dict(
            repo=self.id))
        arch = os.listdir(self.path)[0]
        release = self.release.id_prefix.lower().replace('-', '_')
        master_repomd = config.get('%s_master_repomd' % release)
        repomd = os.path.join(self.path, arch, 'repodata', 'repomd.xml')
        if not os.path.exists(repomd):
            self.log.error('Cannot find local repomd: %s', repomd)
            return
        checksum = hashlib.sha1(file(repomd).read()).hexdigest()
        while True:
            time.sleep(600)
            try:
                masterrepomd = urllib2.urlopen(master_repomd %
                                               self.release.get_version())
            except (urllib2.URLError, urllib2.HTTPError):
                self.log.exception('Error fetching repomd.xml')
                continue
            newsum = hashlib.sha1(masterrepomd.read()).hexdigest()
            if newsum == checksum:
                self.log.info("master repomd.xml matches!")
                notifications.publish(topic="mashtask.sync.done", msg=dict(
                    repo=self.id))
                return

            self.log.debug("master repomd.xml doesn't match! %s != %s for %r",
                           checksum, newsum, self.id)

    def send_notifications(self):
        self.log.info('Sending notifications')
        try:
            agent = os.getlogin()
        except OSError:  # this can happen when building on koji
            agent = u'masher'
        for update in self.updates:
            topic = u'update.complete.%s' % update.status
            notifications.publish(topic=topic, msg=dict(
                update=update, agent=agent,
            ))

    def modify_bugs(self):
        self.log.info('Updating bugs')
        for update in self.updates:
            self.log.debug('Modifying bugs for %s', update.title)
            update.modify_bugs()

    def status_comments(self):
        self.log.info('Commenting on updates')
        for update in self.updates:
            update.status_comment()

    def send_stable_announcements(self):
        self.log.info('Sending stable update announcements')
        for update in self.updates:
            if update.status is UpdateStatus.stable:
                update.send_update_notice()

    def send_testing_digest(self):
        """Send digest mail to mailing lists"""
        self.log.info('Sending updates-testing digest')
        sechead = u'The following %s Security updates need testing:\n Age  URL\n'
        crithead = u'The following %s Critical Path updates have yet to be approved:\n Age URL\n'
        testhead = u'The following builds have been pushed to %s updates-testing\n\n'

        for prefix, content in self.testing_digest.iteritems():
            release = self.db.query(Release).filter_by(long_name=prefix).one()
            test_list_key = '%s_test_announce_list' % (
                release.id_prefix.lower().replace('-', '_'))
            test_list = config.get(test_list_key)
            if not test_list:
                log.warn('%r undefined. Not sending updates-testing digest',
                         test_list_key)
                continue

            log.debug("Sending digest for updates-testing %s" % prefix)
            maildata = u''
            security_updates = self.get_security_updates(prefix)
            if security_updates:
                maildata += sechead % prefix
                for update in security_updates:
                    maildata += u' %3i  %s%s\n' % (
                        update.days_in_testing,
                        config.get('base_address'),
                        update.get_url())
                maildata += '\n\n'

            critpath_updates = self.get_unapproved_critpath_updates(prefix)
            if critpath_updates:
                maildata += crithead % prefix
                for update in self.get_unapproved_critpath_updates(prefix):
                    maildata += u' %3i  %s%s\n' % (
                        update.days_in_testing,
                        config.get('base_address'),
                        update.get_url())
                maildata += '\n\n'

            maildata += testhead % prefix
            updlist = content.keys()
            updlist.sort()
            for pkg in updlist:
                maildata += u'    %s\n' % pkg
            maildata += u'\nDetails about builds:\n\n'
            for nvr in updlist:
                maildata += u"\n" + self.testing_digest[prefix][nvr]

            mail.send_mail(config.get('bodhi_email'), test_list,
                           '%s updates-testing report' % prefix, maildata)

    def get_security_updates(self, release):
        release = self.db.query(Release).filter_by(long_name=release).one()
        updates = self.db.query(Update).filter(
                Update.type == UpdateType.security,
                Update.status == UpdateStatus.testing,
                Update.release == release,
                Update.request == None
        ).all()
        updates = self.sort_by_days_in_testing(updates)
        return updates

    def get_unapproved_critpath_updates(self, release):
        release = self.db.query(Release).filter_by(long_name=release).one()
        updates = self.db.query(Update).filter_by(
            critpath=True,
            status=UpdateStatus.testing,
            request=None,
            release=release,
        ).order_by(Update.date_submitted.desc()).all()
        updates = self.sort_by_days_in_testing(updates)
        return updates

    def sort_by_days_in_testing(self, updates):
        updates = list(updates)
        updates.sort(key=lambda update: update.days_in_testing, reverse=True)
        return updates


class MashThread(threading.Thread):

    def __init__(self, tag, outputdir, comps, previous):
        super(MashThread, self).__init__()
        self.tag = tag
        self.success = False
        mash_cmd = 'mash -o {outputdir} -c {config} -f {compsfile} {tag}'
        mash_conf = config.get('mash_conf', '/etc/mash/mash.conf')
        if os.path.exists(previous):
            mash_cmd += ' -p {}'.format(previous)
        self.mash_cmd = mash_cmd.format(outputdir=outputdir, config=mash_conf,
                                        compsfile=comps, tag=self.tag).split()

    def run(self):
        start = time.time()
        log.info('Mashing %s', self.tag)
        try:
            util.cmd(self.mash_cmd)
            log.info('Took %s seconds to mash %s', time.time() - start,
                     self.tag)
            self.success = True
        except:
            log.exception('There was a problem running mash')
