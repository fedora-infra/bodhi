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
import pyramid.paster

from collections import defaultdict

from bodhi import log, buildsys
from bodhi.util import sorted_updates
from bodhi.config import config, get_configfile
from bodhi.models import Update, UpdateRequest, UpdateType, Release, UpdateStatus

CONFIG = get_configfile()


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

    """
    config_key = 'masher'

    def __init__(self, hub, *args, **kw):
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
        env = pyramid.paster.bootstrap(CONFIG)
        self.db = env['request'].db
        body = msg['body']['msg']

        if self.valid_signer:
            if not fedmsg.crypto.validate_signed_by(msg, self.valid_signer,
                                                    **self.hub.config):
                self.log.error('Received message with invalid signature! Ignoring.')
                # TODO: send email notifications
                return

        releases = self.load_updates(body)

        # Fire off seperate masher threads for each tag being mashed
        threads = []
        for release in releases:
            for request, updates in releases[release].items():
                thread = MasherThread(release, request, updates, self.log)
                threads.append(thread)
                thread.start()
        for thread in threads:
            thread.join()

        env['closer']()
        self.log.info('Push complete!')

    def load_updates(self, body):
        # {Release: {UpdateRequest: [Update,]}}
        releases = defaultdict(lambda: defaultdict(list))
        for title in body['updates'].split():
            update = self.db.query(Update).filter_by(title=title).first()
            if update:
                releases[update.release.name][update.request.value].append(update.title)
            else:
                log.warn('Cannot find update: %s' % title)
        return releases


class MasherThread(threading.Thread):

    def __init__(self, release, request, updates, log):
        super(MasherThread, self).__init__()
        self.log = log
        self.env = pyramid.paster.bootstrap(CONFIG)
        self.db = db = self.env['request'].db
        self.release = db.query(Release).filter_by(name=release).one()
        self.id = getattr(self.release, '%s_tag' % request)
        self.request = UpdateRequest.from_string(request)
        self.updates = set()
        self.state = {
            'tagged': False,
            'updates': updates,
            'completed_repos': []
        }

    def run(self):
        log.info('Running MasherThread(%s)' % self.id)
        try:
            self.save_state()
            # Normally safe_to_move/safe_to_resume happens here...
            # Ideally, we should be able to trust our internal state
        except:
            self.log.exception('Exception in MasherThread(%s)' % self.id)
        finally:
            self.finish()

    def save_state(self):
        """ Save the state of this push so it can be resumed later if necessary """
        mashed_dir = config.get('mashed_dir')
        mash_lock = os.path.join(mashed_dir, 'MASHING-%s' % self.id)
        if os.path.exists(mash_lock):
            self.log.error('Masher lock already exists: %s' % mash_lock)
            raise Exception
        with file(mash_lock, 'w') as lock:
            json.dump(self.state, lock)
        self.log.info('Masher lock created: %s' % mash_lock)

    def finish(self):
        self.env['closer']()
        self.log.info('Thread(%s) finished' % self.id)
