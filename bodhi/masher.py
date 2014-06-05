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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import json
import threading
import fedmsg.consumers

from collections import defaultdict

from bodhi import log, buildsys
from bodhi.util import sorted_updates
from bodhi.config import config
from bodhi.models import (Update, UpdateRequest, UpdateType, Release,
                          UpdateStatus, ReleaseState)


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
    - Update security bug titles
    - Move build tags
    - Expire buildroot overrides
    - Remove pending tags
===
    - mash
    - request_complete
    - Add testing updates to updates-testing digest
    - Generate/update updateinfo.xml and inject it into the repodata
    - Sanity check the repo
    - Flip the symlinks to the new repo
    - Cache the latest repodata
    - Wait for the repo to hit the master mirror
    - Update bugzillas
    - Add comments to updates
    - Generate and email stable update notices
    - Email updates-testing digest
    - Unlock repo
        - unlock updates
        - see if any updates now meet the stable criteria, and set the request
    - Send fedmsgs

TODO:
    - clean up old testing tags for pending releases after X days?
    if there is already a masher lock, merge it with the current push????
    """
    config_key = 'masher'

    def __init__(self, hub, db_factory, *args, **kw):
        self.db_factory = db_factory
        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = prefix + '.' + env + '.' + hub.config.get('masher_topic')
        self.valid_signer = config.get('releng_fedmsg_certname')
        if not self.valid_signer:
            log.warn('No releng_fedmsg_certname defined. Cert validation disabled')
        super(Masher, self).__init__(hub, *args, **kw)
        log.info('Bodhi masher listening on topic: %s' % self.topic)

    def consume(self, msg):
        self.log.info(msg)
        with self.db_factory() as session:
            self.work(session, msg)

    def work(self, session, msg):
        body = msg['body']['msg']

        if self.valid_signer:
            if not fedmsg.crypto.validate_signed_by(msg, self.valid_signer,
                                                    **self.hub.config):
                self.log.error('Received message with invalid signature! Ignoring.')
                # TODO: send email notifications
                return

        releases = self.organize_updates(session, body)

        # Fire off seperate masher threads for each tag being mashed
        threads = []
        for release in releases:
            for request, updates in releases[release].items():
                thread = MasherThread(release, request, updates, self.log, self.db_factory)
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
                releases[update.release.name][update.request.value].append(update.title)
            else:
                log.warn('Cannot find update: %s' % title)
        return releases


class MasherThread(threading.Thread):

    def __init__(self, release, request, updates, log, db_factory, resume=False):
        super(MasherThread, self).__init__()
        self.db_factory = db_factory
        self.log = log
        self.request = UpdateRequest.from_string(request)
        self.release = release
        self.resume = resume
        self.updates = set()
        self.add_tags = []
        self.move_tags = []
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
        self.release = self.db.query(Release).filter_by(name=self.release).one()
        self.id = getattr(self.release, '%s_tag' % self.request.value)
        self.log.info('Running MasherThread(%s)' % self.id)

        try:
            #self.save_state()
            self.load_updates()

            if not self.resume:
                self.lock_updates()
                self.update_security_bugs()
                self.determine_tag_actions()
                self.perform_tag_actions()
                self.expire_buildroot_overrides()
                self.remove_pending_tags()
        except:
            self.log.exception('Exception in MasherThread(%s)' % self.id)
            #self.save_state()
        finally:
            self.finish()

    def load_updates(self):
        self.log.debug('Locking updates')
        updates = []
        for title in self.state['updates']:
            update = self.db.query(Update).filter_by(title=title).first()
            if update:
                updates.append(update)
        self.updates = updates

    def lock_updates(self):
        for update in self.updates:
            update.locked = True
        self.db.flush()

    def save_state(self):
        """Save the state of this push so it can be resumed later if necessary"""
        mashed_dir = config.get('mashed_dir')
        mash_lock = os.path.join(mashed_dir, 'MASHING-%s' % self.id)
        if os.path.exists(mash_lock):
            self.log.error('Masher lock already exists: %s' % mash_lock)
            raise Exception
        with file(mash_lock, 'w') as lock:
            json.dump(self.state, lock)
        self.log.info('Masher lock created: %s' % mash_lock)

    def finish(self):
        self.log.info('Thread(%s) finished' % self.id)

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
                    self.move_tags.append((from_tag, update.requested_tag, build.nvr))

    def perform_tag_actions(self):
        self.koji.multicall = True
        for action in self.add_tags:
            tag, build = action
            self.log.info("Adding tag %s to %s" % (tag, build))
            self.koji.tagBuild(tag, build, force=True)
        for action in self.move_tags:
            from_tag, to_tag, build = action
            self.log.info('Moving %s from %s to %s' % (build, from_tag, to_tag))
            self.koji.moveBuild(from_tag, to_tag, build, force=True)
        results = self.koji.multiCall()
        failed_tasks = buildsys.wait_for_tasks([task[0] for task in results])
        if failed_tasks:
            raise Exception("Failed to move builds: %s" % failed_tasks)
        self.state['tagged'] = True

    def expire_buildroot_overrides(self):
        """ Obsolete any buildroot overrides that are in this push """
        for update in self.updates:
            if update.request is UpdateRequest.stable:
                for build in update.builds:
                    build.override.expire()

    def remove_pending_tags(self):
        """ Remove all pending tags from these updates """
        log.debug("Removing pending tags from builds")
        self.koji.multicall = True
        for update in self.updates:
            if update.request is UpdateRequest.stable:
                update.remove_tag(update.release.pending_stable_tag, koji=self.koji)
            elif update.request is UpdateRequest.testing:
                update.remove_tag(update.release.pending_testing_tag, koji=self.koji)
        result = self.koji.multiCall()
        log.debug('result = %r' % result)
