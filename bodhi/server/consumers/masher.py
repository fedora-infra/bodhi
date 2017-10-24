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

import functools
import hashlib
import json
import glob
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib2
from datetime import datetime

from pyramid.paster import get_appsettings
from sqlalchemy import engine_from_config
import fedmsg.consumers
import jinja2

from bodhi.server import bugs, log, buildsys, notifications, mail
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from bodhi.server.metadata import UpdateInfoMetadata
from bodhi.server.models import (Update, UpdateRequest, UpdateType, Release,
                                 UpdateStatus, ReleaseState, Base, ContentType)
from bodhi.server.util import sorted_updates, sanity_check_repodata, transactional_session_maker


def checkpoint(method):
    """ A decorator for skipping sections of the mash when resuming. """

    key = method.__name__

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.resume or not self.state.get(key):
            # Call it
            retval = method(self, *args, **kwargs)
            if retval is not None:
                raise ValueError("checkpointed functions may not return stuff")
            # if it didn't raise an exception, mark the checkpoint
            self.state[key] = True
            self.save_state()
        else:
            # cool!  we don't need to do anything, since we ran last time
            pass

        return None
    return wrapper


def request_order_key(requestblob):
    """This generates a sort key for the updates documents in generate_batches

    Args:
        requestblob: A dictionary as described in generate_batches

    Returns:
        int: Ordering key for this batch.

    The key comes down to:
        Stable + security: -3
        Testing + security: -2
        Stable: -1
        Testing: 0
    """
    value = 0
    if requestblob['has_security']:
        value -= 2
    if requestblob['phase'] == 'stable':
        value -= 1
    return value


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

    def __init__(self, hub, db_factory=None, mash_dir=config.get('mash_dir'),
                 *args, **kw):
        if not db_factory:
            config_uri = '/etc/bodhi/production.ini'
            settings = get_appsettings(config_uri)
            engine = engine_from_config(settings, 'sqlalchemy.')
            Base.metadata.create_all(engine)
            self.db_factory = transactional_session_maker()
        else:
            self.db_factory = db_factory

        buildsys.setup_buildsystem(config)
        bugs.set_bugtracker()
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
            if not fedmsg.crypto.validate_signed_by(msg['body'], self.valid_signer,
                                                    **self.hub.config):
                self.log.error('Received message with invalid signature!'
                               'Ignoring.')
                # TODO: send email notifications
                return

        self.work(msg)

    def generate_batches(self, session, update_titles):
        """Generate a sorted list of batches to perform.

        Args:
            session: Database transaction
            update_titles: List of models.Update.title

        Returns:
            list: A list of dictionaries with the following keys:
                title: Name of the "batch" ("f27-stable")
                contenttype: instance of models.ContentType
                updates: list of models.Update instances
                phase: "stable" | "testing"
                has_security: bool

        Raises:
            ValueError: If a submitted update could not be found
            ValueError: if updates exist with multiple types of builds
        """
        work = {}
        for title in update_titles:
            update = session.query(Update).filter_by(title=title).one()
            if not update.request:
                self.log.info('%s request was revoked', update.title)
                continue
            update.locked = True
            update.date_locked = datetime.utcnow()
            # ASSUMPTION: For now, updates can only be of a single type.
            ctype = None
            for build in update.builds:
                if ctype is None:
                    ctype = build.type
                elif ctype is not build.type:  # pragma: no cover
                    # This branch is not covered because the Update.validate_builds validator
                    # catches the same assumption breakage. This check here is extra for the
                    # time when someone adds multitype updates and forgets to update this.
                    raise ValueError('Builds of multiple types found in %s'
                                     % title)
            # This key is just to insert things in the same place in the "work"
            # dict.
            key = '%s-%s-%s' % (update.release.name, update.request.value,
                                ctype.value)
            if key in work:
                work[key]['updates'].append(title)
                work[key]['has_security'] = (
                    work[key]['has_security'] or (update.type is UpdateType.security))
            else:
                work[key] = {'title': '%s-%s' % (update.release.name,
                                                 update.request.value),
                             'contenttype': ctype,
                             'updates': [title],
                             'phase': update.request.value,
                             'release': update.release.name,
                             'request': update.request.value,
                             'has_security': update.type is UpdateType.security}

        # Now that we have a full list of all the release-request-ctype requests, let's sort them
        batches = work.values()
        batches.sort(key=request_order_key)
        return batches

    def work(self, msg):
        """Begin the push process.

        Here we organize & prioritize the updates, and fire off separate
        threads for each reop tag being mashed.

        If there are any security updates in the push, then those repositories
        will be executed before all others.
        """
        body = msg['body']['msg']
        resume = body.get('resume', False)
        agent = body.get('agent')
        notifications.publish(topic="mashtask.start", msg=dict(agent=agent), force=True)

        with self.db_factory() as session:
            batches = self.generate_batches(session, body['updates'])

        results = []
        # Important repos first, then normal
        last_key = None
        threads = []
        for batch in batches:
            if last_key is not None and request_order_key(batch) != last_key:
                # This means that after we submit all Stable+Security updates, we wait with kicking
                # off the next series of mashes until that finishes.
                self.log.info('All mashes for priority %s running, waiting', last_key)
                for thread in threads:
                    thread.join()
                    for result in thread.results():
                        results.append(result)

            last_key = request_order_key(batch)
            self.log.info('Now starting mashes for priority %s', last_key)

            masher = get_masher(batch['contenttype'])
            if not masher:
                self.log.error('Unsupported content type %s submitted for mashing. SKIPPING',
                               batch['contenttype'].value)
                continue

            self.log.info('Starting masher type %s for %s with %d updates',
                          masher, batch['title'], len(batch['updates']))
            thread = masher(batch['release'], batch['request'], batch['updates'], agent, self.log,
                            self.db_factory, self.mash_dir, resume)
            threads.append(thread)
            thread.start()

        self.log.info('All of the batches are running. Now waiting for the final results')
        for thread in threads:
            thread.join()
            for result in thread.results():
                results.append(result)

        self.log.info('Push complete!  Summary follows:')
        for result in results:
            self.log.info(result)


def get_masher(content_type):
    """Function to return the correct MasherThread subclass for content_type."""
    mashers = [RPMMasherThread, ModuleMasherThread]
    for possible in mashers:
        if possible.ctype is content_type:
            return possible


class MasherThread(threading.Thread):
    """The base class that defines common things for all mashings."""
    ctype = None
    pungi_template_config_key = None

    def __init__(self, release, request, updates, agent,
                 log, db_factory, mash_dir, resume=False):
        super(MasherThread, self).__init__()
        self.db_factory = db_factory
        self.log = log
        self.agent = agent
        self.mash_dir = mash_dir
        self.request = UpdateRequest.from_string(request)
        self.release = release
        self.resume = resume
        self.updates = set()
        self.add_tags_async = []
        self.move_tags_async = []
        self.add_tags_sync = []
        self.move_tags_sync = []
        self.testing_digest = {}
        self.path = None
        self.state = {
            'updates': updates,
            'completed_repos': []
        }
        self.success = False
        self.devnull = None
        self._startyear = None

    def run(self):
        try:
            with self.db_factory() as session:
                self.db = session
                self.work()
                self.db = None
        except:
            self.log.exception('MasherThread failed. Transaction rolled back.')

    def results(self):
        attrs = ['name', 'success']
        yield "  name:  %(name)-20s  success:  %(success)s" % dict(
            zip(attrs, [getattr(self, attr, 'Undefined') for attr in attrs])
        )

    def work(self):
        self.release = self.db.query(Release)\
                              .filter_by(name=self.release).one()
        self.id = getattr(self.release, '%s_tag' % self.request.value)

        # Set our thread's "name" so it shows up nicely in the logs.
        # https://docs.python.org/2/library/threading.html#thread-objects
        self.name = self.id

        # For 'pending' branched releases, we only want to perform repo-related
        # tasks for testing updates. For stable updates, we should just add the
        # dist_tag and do everything else other than mashing/updateinfo, since
        # the nightly build-branched cron job mashes for us.
        self.skip_mash = False
        if (self.release.state is ReleaseState.pending and
                self.request is UpdateRequest.stable):
            self.skip_mash = True

        self.log.info('Running MasherThread(%s)' % self.id)
        self.init_state()

        notifications.publish(
            topic="mashtask.mashing",
            msg=dict(repo=self.id,
                     updates=self.state['updates'],
                     agent=self.agent,
                     ctype=self.ctype.value),
            force=True,
        )

        try:
            if self.resume:
                self.load_state()
            else:
                self.save_state()

            self.load_updates()
            self.verify_updates()

            if self.request is UpdateRequest.stable:
                self.perform_gating()

            self.determine_and_perform_tag_actions()

            self.update_security_bugs()

            self.expire_buildroot_overrides()
            self.remove_pending_tags()

            if not self.skip_mash:
                mash_process = self.mash()

            # Things we can do while we're mashing
            self.complete_requests()
            self.generate_testing_digest()

            if not self.skip_mash:
                uinfo = self.generate_updateinfo()

                self.wait_for_mash(mash_process)

                uinfo.insert_updateinfo(self.path)

            if not self.skip_mash:
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

            self.success = True
            self.remove_state()
            self.unlock_updates()

            self.check_all_karma_thresholds()
            self.obsolete_older_updates()

        except:
            self.log.exception('Exception in MasherThread(%s)' % self.id)
            self.save_state()
            raise
        finally:
            self.finish(self.success)

    def load_updates(self):
        self.log.debug('Loading updates')
        updates = []
        for title in self.state['updates']:
            update = self.db.query(Update).filter_by(title=title).one()
            updates.append(update)
        if not updates:
            raise Exception('Unable to load updates: %r' %
                            self.state['updates'])
        self.updates = updates

    def unlock_updates(self):
        self.log.debug('Unlocking updates')
        for update in self.updates:
            update.locked = False
            update.date_locked = None
        self.db.flush()

    def check_all_karma_thresholds(self):
        """
        If we just pushed testing updates see if any of them now meet either of
        the karma thresholds
        """
        if self.request is UpdateRequest.testing:
            self.log.info('Determing if any testing updates reached the karma '
                          'thresholds during the push')
            for update in self.updates:
                try:
                    update.check_karma_thresholds(self.db, agent=u'bodhi')
                except BodhiException:
                    self.log.exception('Problem checking karma thresholds')

    def obsolete_older_updates(self):
        """
        Obsolete any older updates that may still be lying around.
        """
        self.log.info('Checking for obsolete updates')
        for update in self.updates:
            update.obsolete_older_updates(self.db)

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
        log.warn(text)
        update.comment(self.db, text, author=u'bodhi')
        # Remove the pending tag as well
        if update.request is UpdateRequest.stable:
            update.remove_tag(update.release.pending_stable_tag,
                              koji=buildsys.get_session())
        elif update.request is UpdateRequest.testing:
            update.remove_tag(update.release.pending_testing_tag,
                              koji=buildsys.get_session())
        update.request = None
        if update.title in self.state['updates']:
            self.state['updates'].remove(update.title)
        if update in self.updates:
            self.updates.remove(update)
        notifications.publish(
            topic="update.eject",
            msg=dict(
                repo=self.id,
                update=update,
                reason=reason,
                request=self.request,
                release=self.release,
                agent=self.agent,
            ),
            force=True,
        )

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

    def load_state(self):
        """
        Load the state of this push so it can be resumed later if necessary
        """
        with file(self.mash_lock) as lock:
            self.state = json.load(lock)
        self.log.info('Masher state loaded from %s', self.mash_lock)
        self.log.info(self.state)
        for path in self.state['completed_repos']:
            if self.id in path:
                self.path = path
                self.log.info('Resuming push with completed repo: %s' % self.path)
                return
        self.log.info('Resuming push without any completed repos')

    def remove_state(self):
        self.log.info('Removing state: %s', self.mash_lock)
        os.remove(self.mash_lock)

    def finish(self, success):
        if hasattr(self, '_pungi_conf_dir') and os.path.exists(self._pungi_conf_dir) and success:
            # Let's clean up the pungi configs we wrote
            shutil.rmtree(self._pungi_conf_dir)

        self.log.info('Thread(%s) finished.  Success: %r' % (self.id, success))
        notifications.publish(
            topic="mashtask.complete",
            msg=dict(success=success, repo=self.id, agent=self.agent, ctype=self.ctype.value),
            force=True,
        )

    def update_security_bugs(self):
        """Update the bug titles for security updates"""
        self.log.info('Updating bug titles for security updates')
        for update in self.updates:
            if update.type is UpdateType.security:
                for bug in update.bugs:
                    bug.update_details()

    @checkpoint
    def determine_and_perform_tag_actions(self):
        self._determine_tag_actions()
        self._perform_tag_actions()

    def _determine_tag_actions(self):
        tag_types, tag_rels = Release.get_tags(self.db)
        # sync & async tagging batches
        for i, batch in enumerate(sorted_updates(self.updates)):
            for update in batch:
                add_tags = []
                move_tags = []

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
                        reason = 'Cannot find relevant tag for %s.  None of %s are in %s.'
                        reason = reason % (build.nvr, tags, tag_types[status])
                        self.eject_from_mash(update, reason)
                        break

                    if self.skip_mash:
                        add_tags.append((update.requested_tag, build.nvr))
                    else:
                        move_tags.append((from_tag, update.requested_tag,
                                          build.nvr))
                else:
                    if i == 0:
                        self.add_tags_sync.extend(add_tags)
                        self.move_tags_sync.extend(move_tags)
                    else:
                        self.add_tags_async.extend(add_tags)
                        self.move_tags_async.extend(move_tags)

    def _perform_tag_actions(self):
        koji = buildsys.get_session()
        for i, batches in enumerate([(self.add_tags_sync, self.move_tags_sync),
                                     (self.add_tags_async, self.move_tags_async)]):
            add, move = batches
            if i == 0:
                koji.multicall = False
            else:
                koji.multicall = True
            for action in add:
                tag, build = action
                self.log.info("Adding tag %s to %s" % (tag, build))
                koji.tagBuild(tag, build, force=True)
            for action in move:
                from_tag, to_tag, build = action
                self.log.info('Moving %s from %s to %s' % (
                              build, from_tag, to_tag))
                koji.moveBuild(from_tag, to_tag, build, force=True)

            if i != 0:
                results = koji.multiCall()
                failed_tasks = buildsys.wait_for_tasks([task[0] for task in results],
                                                       koji, sleep=15)
                if failed_tasks:
                    raise Exception("Failed to move builds: %s" % failed_tasks)

    def expire_buildroot_overrides(self):
        """ Expire any buildroot overrides that are in this push """
        for update in self.updates:
            if update.request is UpdateRequest.stable:
                for build in update.builds:
                    if build.override:
                        try:
                            build.override.expire()
                        except:
                            log.exception('Problem expiring override')

    def remove_pending_tags(self):
        """ Remove all pending tags from these updates """
        self.log.debug("Removing pending tags from builds")
        koji = buildsys.get_session()
        koji.multicall = True
        for update in self.updates:
            if update.request is UpdateRequest.stable:
                update.remove_tag(update.release.pending_stable_tag,
                                  koji=koji)
            elif update.request is UpdateRequest.testing:
                update.remove_tag(update.release.pending_testing_tag,
                                  koji=koji)
        result = koji.multiCall()
        self.log.debug('remove_pending_tags koji.multiCall result = %r',
                       result)

    def copy_additional_pungi_files(self, pungi_conf_dir, template_env):
        raise NotImplementedError

    def create_pungi_config(self):
        loader = jinja2.FileSystemLoader(searchpath=config.get('pungi.basepath'))
        env = jinja2.Environment(loader=loader,
                                 autoescape=False,
                                 block_start_string='[%',
                                 block_end_string='%]',
                                 variable_start_string='[[',
                                 variable_end_string=']]',
                                 comment_start_string='[#',
                                 comment_end_string='#]')

        env.globals['id'] = self.id
        env.globals['release'] = self.release
        env.globals['request'] = self.request
        env.globals['updates'] = self.updates

        config_template = config.get(self.pungi_template_config_key)
        template = env.get_template(config_template)

        self._pungi_conf_dir = tempfile.mkdtemp(prefix='bodhi-pungi-%s-' % self.id)

        with open(os.path.join(self._pungi_conf_dir, 'pungi.conf'), 'w') as conffile:
            conffile.write(template.render())

        self.copy_additional_pungi_files(self._pungi_conf_dir, env)

    def mash(self):
        if self.path and self.path in self.state['completed_repos']:
            self.log.info('Skipping completed repo: %s', self.path)
            return

        # We have a thread-local devnull FD so that we can close them after the mash is done
        self.devnull = open(os.devnull, 'wb')

        self.create_pungi_config()
        config_file = os.path.join(self._pungi_conf_dir, 'pungi.conf')
        self._label = '%s-%s' % (config.get('pungi.labeltype'),
                                 datetime.utcnow().strftime('%Y%m%d.%H%M'))
        pungi_cmd = [config.get('pungi.cmd'),
                     '--config', config_file,
                     '--quiet',
                     '--target-dir', self.mash_dir,
                     '--old-composes', self.mash_dir,
                     '--no-latest-link',
                     '--label', self._label]
        pungi_cmd += config.get('pungi.extracmdline')

        self.log.info('Running the pungi command: %s', pungi_cmd)
        mash_process = subprocess.Popen(pungi_cmd,
                                        # Nope. No shell for you
                                        shell=False,
                                        # Should be useless, but just to set something predictable
                                        cwd=self.mash_dir,
                                        # Pungi will logs its stdout into pungi.global.log
                                        stdout=self.devnull,
                                        # Stderr should also go to pungi.global.log if it starts
                                        stderr=subprocess.PIPE,
                                        # We will never have additional input
                                        stdin=self.devnull)
        self.log.info('Pungi running as PID: %s', mash_process.pid)
        # Since the mash process takes a long time, we can safely just wait 3 seconds to abort the
        # entire mash early if Pungi fails to start up correctly.
        time.sleep(3)
        if mash_process.poll() not in [0, None]:
            self.log.error('Pungi process terminated with error within 3 seconds! Abandoning!')
            _, err = mash_process.communicate()
            self.log.error('Stderr: %s', err)
            self.devnull.close()
            raise Exception('Pungi returned error, aborting!')

        # This is used to find the generated directory post-mash.
        # This is stored at the time of start so that even if the update run crosses the year
        # border, we can still find it back.
        self._startyear = datetime.utcnow().year

        return mash_process

    def wait_for_mash(self, mash_process):
        if mash_process is None:
            self.log.info('Not waiting for mash thread, as there was no mash')
            return
        self.log.info('Waiting for mash thread to finish')
        _, err = mash_process.communicate()
        self.devnull.close()
        if mash_process.returncode != 0:
            self.log.error('Mashing process exited with exit code %d', mash_process.returncode)
            self.log.error('Stderr: %s', err)
            raise Exception('Pungi exited with status %d' % mash_process.returncode)
        else:
            self.log.info('Mashing finished')

        # Find the path Pungi just created
        requesttype = 'updates'
        if self.request is UpdateRequest.testing:
            requesttype = 'updates-testing'
        # The year here is used so that we can correctly find the latest updates mash, so that we
        # find updates-20420101.1 instead of updates-testing-20420506.5
        prefix = '%s-%d-%s-%s*' % (self.release.id_prefix.title(),
                                   int(self.release.version),
                                   requesttype,
                                   self._startyear)

        paths = glob.glob(os.path.join(self.mash_dir, prefix))
        paths.sort()
        if len(paths) < 1:
            raise Exception('We were unable to find a path with prefix %s in mashdir' % prefix)
        self.log.debug('Paths: %s', paths)
        self.path = paths[-1]
        self.state['completed_repos'].append(self.path)
        self.save_state()

    def complete_requests(self):
        """Mark all the updates as pushed using Update.request_complete()."""
        self.log.info("Running post-request actions on updates")
        for update in self.updates:
            if update.request:
                update.request_complete()
            else:
                self.log.warn('Update %s missing request', update.title)

    def add_to_digest(self, update):
        """Add an package to the digest dictionary.

        {'release-id': {'build nvr': body text for build, ...}}

        Args:
            update (bodhi.server.models.Update): The update to add to the dict.
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
        self.log.info('Testing digest generation for %s complete' % self.release.name)

    def generate_updateinfo(self):
        self.log.info('Generating updateinfo for %s' % self.release.name)
        uinfo = UpdateInfoMetadata(self.release, self.request,
                                   self.db, self.mash_dir)
        self.log.info('Updateinfo generation for %s complete' % self.release.name)
        return uinfo

    def sanity_check_repo(self):
        """Sanity check our repo.

            - make sure we didn't compose a repo full of symlinks
            - sanity check our repodata

        This basically checks that pungi was run with gather_method='hardlink-or-copy' so that
        we get a repository with either hardlinks or copied files.
        This means that we when we go and sync generated repositories out, we do not need to take
        special case to copy the target files rather than symlinks.
        """
        self.log.info("Running sanity checks on %s" % self.path)

        arches = os.listdir(os.path.join(self.path, 'compose', 'Everything'))
        for arch in arches:
            # sanity check our repodata
            try:
                if arch == 'source':
                    repodata = os.path.join(self.path, 'compose',
                                            'Everything', arch, 'tree', 'repodata')
                else:
                    repodata = os.path.join(self.path, 'compose',
                                            'Everything', arch, 'os', 'repodata')
                sanity_check_repodata(repodata)
            except Exception:
                self.log.exception("Repodata sanity check failed!")
                raise

            # make sure that pungi didn't symlink our packages
            try:
                if arch == 'source':
                    dirs = [('tree', 'Packages')]
                else:
                    dirs = [('debug', 'tree', 'Packages'), ('os', 'Packages')]

                # Example of full path we are checking:
                # self.path/compose/Everything/os/Packages/s/something.rpm
                for checkdir in dirs:
                    checkdir = os.path.join(self.path, 'compose', 'Everything', arch, *checkdir)
                    subdirs = os.listdir(checkdir)
                    # subdirs is the self.path/compose/Everything/os/Packages/{a,b,c,...}/ dirs
                    #
                    # Let's check the first file in each subdir. If they are correct, we'll assume
                    # the rest is correct
                    # This is to avoid tons and tons of IOPS for a bunch of files put in in the
                    # same way
                    for subdir in subdirs:
                        for checkfile in os.listdir(os.path.join(checkdir, subdir)):
                            if not checkfile.endswith('.rpm'):
                                continue
                            if os.path.islink(os.path.join(checkdir, subdir, checkfile)):
                                self.log.error('Pungi out directory contains at least one '
                                               'symlink at %s', checkfile)
                                raise Exception('Symlinks found')
                            # We have checked the first rpm in the subdir
                            break
            except Exception:
                self.log.exception('Unable to check pungi mashed repositories')
                raise

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
        self.log.info("Creating symlink: %s => %s" % (link, self.path))
        os.symlink(self.path, link)

    def wait_for_sync(self):
        """Block until our repomd.xml hits the master mirror"""
        self.log.info('Waiting for updates to hit the master mirror')
        notifications.publish(
            topic="mashtask.sync.wait",
            msg=dict(repo=self.id, agent=self.agent),
            force=True,
        )
        mash_path = os.path.join(self.path, 'compose', 'Everything')
        checkarch = None
        # Find the first non-source arch to check against
        for arch in os.listdir(mash_path):
            if arch == 'source':
                continue
            checkarch = arch
            break
        if not checkarch:
            raise Exception('Not found an arch to wait_for_sync with')

        repomd = os.path.join(mash_path, arch, 'os', 'repodata', 'repomd.xml')
        if not os.path.exists(repomd):
            self.log.error('Cannot find local repomd: %s', repomd)
            return

        master_repomd_url = self._get_master_repomd_url(arch)

        with open(repomd) as repomdf:
            checksum = hashlib.sha1(repomdf.read()).hexdigest()
        while True:
            try:
                self.log.info('Polling %s' % master_repomd_url)
                masterrepomd = urllib2.urlopen(master_repomd_url)
            except (urllib2.URLError, urllib2.HTTPError):
                self.log.exception('Error fetching repomd.xml')
                time.sleep(200)
                continue
            newsum = hashlib.sha1(masterrepomd.read()).hexdigest()
            if newsum == checksum:
                self.log.info("master repomd.xml matches!")
                notifications.publish(
                    topic="mashtask.sync.done",
                    msg=dict(repo=self.id, agent=self.agent),
                    force=True,
                )
                return

            self.log.debug("master repomd.xml doesn't match! %s != %s for %r",
                           checksum, newsum, self.id)
            time.sleep(200)

    def send_notifications(self):
        self.log.info('Sending notifications')
        try:
            agent = os.getlogin()
        except OSError:  # this can happen when building on koji
            agent = u'masher'
        for update in self.updates:
            topic = u'update.complete.%s' % update.status
            notifications.publish(
                topic=topic,
                msg=dict(update=update, agent=agent),
                force=True,
            )

    @checkpoint
    def modify_bugs(self):
        self.log.info('Updating bugs')
        for update in self.updates:
            self.log.debug('Modifying bugs for %s', update.title)
            update.modify_bugs()

    def status_comments(self):
        self.log.info('Commenting on updates')
        for update in self.updates:
            update.status_comment(self.db)

    @checkpoint
    def send_stable_announcements(self):
        self.log.info('Sending stable update announcements')
        for update in self.updates:
            if update.status is UpdateStatus.stable:
                update.send_update_notice()

    @checkpoint
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
                    maildata += u' %3i  %s   %s\n' % (
                        update.days_in_testing,
                        update.abs_url(),
                        update.title)
                maildata += '\n\n'

            critpath_updates = self.get_unapproved_critpath_updates(prefix)
            if critpath_updates:
                maildata += crithead % prefix
                for update in self.get_unapproved_critpath_updates(prefix):
                    maildata += u' %3i  %s   %s\n' % (
                        update.days_in_testing,
                        update.abs_url(),
                        update.title)
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
            Update.request.is_(None)
        ).all()
        updates = self.sort_by_days_in_testing(updates)
        return updates

    def get_unapproved_critpath_updates(self, release):
        """
        Return a list of unapproved critical path updates for the given release.

        Builds a query for critical path updates that are testing and do not have a request, and
        then returns a list of the query results reverse sorted by the number of days they have been
        in testing.

        Args:
            release (basestring): The long_name of the Release to be queried.
        Return:
            list: The list of unapproved critical path updates for the given release.
        """
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
        """
        Sort the given updates by the number of days they have been in testing, reversed.

        Args:
            updates (iterable): The updates to be sorted.
        Return:
            list: The sorted updates.
        """
        updates = list(updates)
        updates.sort(key=lambda update: update.days_in_testing, reverse=True)
        return updates

    def _get_master_repomd_url(self, arch):
        """
        Return the master repomd URL for the given arch.

        Look up the correct *_master_repomd setting in the config and use it to form the URL that
        wait_for_sync() will use to determine when the repository has been synchronized to the
        master mirror.

        Args:
            arch (basestring): The architecture for which a URL needs to be formed.

        Returns:
            basestring: A URL on the master mirror where the repomd.xml file should be synchronized.
        """
        release = self.release.id_prefix.lower().replace('-', '_')
        request = self.request.value

        # If the release has primary_arches defined in the config, we need to consider whether to
        # use the release's *alt_master_repomd setting.
        primary_arches = config.get(
            '{release}_{version}_primary_arches'.format(
                release=release, version=self.release.version))
        if primary_arches and arch not in primary_arches.split():
            key = '%s_%s_alt_master_repomd'
        else:
            key = '%s_%s_master_repomd'
        key = key % (release, request)

        master_repomd = config.get(key)
        if not master_repomd:
            raise ValueError("Could not find %s in the config file" % key)

        return master_repomd % (self.release.version, arch)


class RPMMasherThread(MasherThread):
    ctype = ContentType.rpm
    pungi_template_config_key = 'pungi.conf.rpm'

    def copy_additional_pungi_files(self, pungi_conf_dir, template_env):
        variants_template = template_env.get_template('variants.rpm.xml.j2')

        with open(os.path.join(pungi_conf_dir, 'variants.xml'), 'w') as variantsfile:
            variantsfile.write(variants_template.render())


class ModuleMasherThread(MasherThread):
    ctype = ContentType.module
    pungi_template_config_key = 'pungi.conf.module'

    def copy_additional_pungi_files(self, pungi_conf_dir, template_env):
        template = template_env.get_template('variants.module.xml.j2')

        module_list = self._generate_module_list()

        with open(os.path.join(pungi_conf_dir, 'module-variants.xml'), 'w') as variantsfile:
            variantsfile.write(template.render(modules=module_list))

    def generate_testing_digest(self):
        """Temporarily disable testing digests for modules.

        At some point, we'd want to fill the testing digest for modules too, but we basically
        need to determine what kind of emails we want to send and write templates.
        For now, let's skip this, since the current version tries to read RPM headers, which
        do not exist in the module build objects.
        """
        pass

    def _generate_module_list(self):
        """
        Generates a list of NSV which should be used for pungi modular compose

        Returns:
          list: list of NSV string which should be composed
        """
        newest_builds = {}
        # we loop through builds so we get rid of older builds and get only
        # a dict with the newest builds
        for build in self.release.builds:
            nsv = build.nvr.rsplit('-', 1)
            ns = nsv[0]
            version = nsv[1]

            if ns in newest_builds:
                curr_version = newest_builds[ns]
                if int(curr_version) < int(version):
                    newest_builds[ns] = version
            else:
                newest_builds[ns] = version

        # make sure that the modules we want to update get their correct versions
        for update in self.updates:
            for build in update.builds:
                nsv = build.nvr.rsplit('-', 1)
                ns = nsv[0]
                version = nsv[1]
                newest_builds[ns] = version

        return ["%s-%s" % (nstream, v) for nstream, v in newest_builds.iteritems()]
