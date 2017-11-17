# -*- coding: utf-8 -*-
# Copyright © 2007-2017 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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

import fedmsg.consumers
import jinja2
from six.moves import zip
import six

from bodhi.server import bugs, initialize_db, log, buildsys, notifications, mail
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from bodhi.server.metadata import UpdateInfoMetadata
from bodhi.server.models import (Compose, ComposeState, Update, UpdateRequest, UpdateType, Release,
                                 UpdateStatus, ReleaseState, ContentType)
from bodhi.server.util import sorted_updates, sanity_check_repodata, transactional_session_maker


def checkpoint(method):
    """
    Decorate a method for skipping sections of the mash when resuming.

    Args:
        method (callable): The callable to skip if we are resuming.
    Returns:
        callable: A function that skips the method if it can.
    """
    key = method.__name__

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.resume or not self._checkpoints.get(key):
            # Call it
            retval = method(self, *args, **kwargs)
            if retval is not None:
                raise ValueError("checkpointed functions may not return stuff")
            # if it didn't raise an exception, mark the checkpoint
            self._checkpoints[key] = True
            self.save_state()
        else:
            # cool!  we don't need to do anything, since we ran last time
            pass

        return None
    return wrapper


def request_order_key(compose):
    """
    Generate a sort key for the updates documents in generate_batches.

    Args:
        requestblob (dict): A dictionary as described in generate_batches.

    Returns:
        int: Ordering key for this batch.

    The key comes down to:
        Stable + security: -3
        Testing + security: -2
        Stable: -1
        Testing: 0
    """
    value = 0
    if compose['security']:
        value -= 2
    if compose['request'] == UpdateRequest.stable.value:
        value -= 1
    return value


class Masher(fedmsg.consumers.FedmsgConsumer):
    """
    The Bodhi Masher.

    A fedmsg consumer that listens for messages from releng members.

    An updates "compose" consists of::

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

    Things to do while we're waiting on mash:

    - Add testing updates to updates-testing digest
    - Generate/update updateinfo.xml
    - Have a coffee. Have 7 coffees.

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
        """
        Initialize the Masher.

        Args:
            hub (moksha.hub.hub.CentralMokshaHub): The hub this handler is consuming messages from.
                It is used to look up the hub config values.
            db_factory (bodhi.server.util.TransactionalSessionMaker or None): If given, used as the
                db_factory for this Masher. If None (the default), a new TransactionalSessionMaker
                is created and used.
            mash_dir (basestring): The directory in which to place mashes.
        """
        if not db_factory:
            initialize_db(config)
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
        """
        Receive a fedmsg and call work() with it.

        Args:
            msg (munch.Munch): The fedmsg that was received.
        """
        self.log.info(msg)
        if self.valid_signer:
            if not fedmsg.crypto.validate_signed_by(msg['body'], self.valid_signer,
                                                    **self.hub.config):
                self.log.error('Received message with invalid signature!'
                               'Ignoring.')
                # TODO: send email notifications
                return

        self.work(msg)

    def _get_composes(self, msg):
        """
        Return a list of dictionaries that represent the :class:`Composes <Compose>` we should run.

        This method is compatible with the unversioned masher.start message, and also version 2.
        If no version is found, it will use the updates listed in the message to create new Compose
        objects and return dictionary representations of them.

        This method also marks the Composes as pending, which acknowledges the receipt of the
        message.

        Args:
            msg (munch.Munch): The body of the received fedmsg.
        Returns:
            list: A list of dictionaries, as returned from :meth:`Compose.__json__`.
        """
        with self.db_factory() as db:
            if 'api_version' in msg and msg['api_version'] == 2:
                composes = [Compose.from_dict(db, c) for c in msg['composes']]
            elif 'updates' in msg:
                updates = [db.query(Update).filter(Update.title == t).one() for t in msg['updates']]
                composes = Compose.from_updates(updates)
                for c in composes:
                    db.add(c)
                    # This flush is necessary so the compose finds its updates, which gives it a
                    # content_type when it is serialized later.
                    db.flush()
            else:
                raise ValueError('Unable to process fedmsg: {}'.format(msg))

            for c in composes:
                # Acknowledge that we've received the command to run these composes.
                c.state = ComposeState.pending

            return [c.__json__() for c in composes]

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

        results = []
        # Important repos first, then normal
        last_key = None
        threads = []
        for compose in self._get_composes(body):
            if ((last_key is not None and request_order_key(compose) != last_key) or
                    (len(threads) >= config.get('max_concurrent_mashes'))):
                # This means that after we submit all Stable+Security updates, we wait with kicking
                # off the next series of mashes until that finishes.
                self.log.info('Waiting on %d mashes for priority %s', len(threads), last_key)
                for thread in threads:
                    thread.join()
                    for result in thread.results():
                        results.append(result)
                threads = []

            last_key = request_order_key(compose)
            self.log.info('Now starting mashes for priority %s', last_key)

            masher = get_masher(ContentType.from_string(compose['content_type']))
            if not masher:
                self.log.error('Unsupported content type %s submitted for mashing. SKIPPING',
                               compose['content_type'])
                continue

            thread = masher(compose, agent, self.log, self.db_factory, self.mash_dir, resume)
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
    """
    Return the correct MasherThread subclass for content_type.

    Args:
        content_type (bodhi.server.models.EnumSymbol): The content type we seek a masher for.
    Return:
        MasherThread or None: Either an RPMMasherThread or a ModuleMasherThread, as appropriate, or
            None if no masher is found.
    """
    mashers = [RPMMasherThread, ModuleMasherThread]
    for possible in mashers:
        if possible.ctype is content_type:
            return possible


class MasherThread(threading.Thread):
    """The base class that defines common things for all mashings."""

    ctype = None
    pungi_template_config_key = None

    def __init__(self, compose, agent, log, db_factory, mash_dir, resume=False):
        """
        Initialize the MasherThread.

        Args:
            compose (dict): A dictionary representation of the Compose to run, formatted like the
                output of :meth:`Compose.__json__`.
            agent (basestring): The user who is executing the mash.
            log (logging.Logger): A logger to use for this mash.
            db_factory (bodhi.server.util.TransactionalSessionMaker): A DB session to use while
                mashing.
            mash_dir (basestring): A path to a directory to generate the mash in.
            resume (bool): Whether or not we are resuming a previous failed mash. Defaults to False.
        """
        super(MasherThread, self).__init__()
        self.db_factory = db_factory
        self.log = log
        self.agent = agent
        self.mash_dir = mash_dir
        self._compose = compose
        self.resume = resume
        self.add_tags_async = []
        self.move_tags_async = []
        self.add_tags_sync = []
        self.move_tags_sync = []
        self.testing_digest = {}
        self.path = None
        self.success = False
        self.devnull = None
        self._startyear = None

    def run(self):
        """Run the thread by managing a db transaction and calling work()."""
        try:
            with self.db_factory() as session:
                self.db = session
                self.compose = Compose.from_dict(session, self._compose)
                self._checkpoints = json.loads(self.compose.checkpoints)
                self.log.info('Starting masher type %s for %s with %d updates',
                              self, str(self.compose), len(self.compose.updates))
                self.save_state(ComposeState.initializing)
                self.work()
        except Exception as e:
            with self.db_factory() as session:
                self.db = session
                self.compose = Compose.from_dict(session, self._compose)
                self.compose.error_message = unicode(e)
                self.save_state(ComposeState.failed)

            self.log.exception('MasherThread failed. Transaction rolled back.')
        finally:
            self.compose = None
            self.db = None

    def results(self):
        """
        Yield log string messages about the results of this mash run.

        Yields:
            basestring: A string for human readers indicating the success of the mash.
        """
        attrs = ['name', 'success']
        yield "  name:  %(name)-20s  success:  %(success)s" % dict(
            zip(attrs, [getattr(self, attr, 'Undefined') for attr in attrs])
        )

    def work(self):
        """Perform the various high-level tasks for the mash."""
        self.id = getattr(self.compose.release, '%s_tag' % self.compose.request.value)

        # Set our thread's "name" so it shows up nicely in the logs.
        # https://docs.python.org/2/library/threading.html#thread-objects
        self.name = self.id

        # For 'pending' branched releases, we only want to perform repo-related
        # tasks for testing updates. For stable updates, we should just add the
        # dist_tag and do everything else other than mashing/updateinfo, since
        # the nightly build-branched cron job mashes for us.
        self.skip_mash = False
        if (self.compose.release.state is ReleaseState.pending and
                self.compose.request is UpdateRequest.stable):
            self.skip_mash = True

        self.log.info('Running MasherThread(%s)' % self.id)
        self.init_state()

        notifications.publish(
            topic="mashtask.mashing",
            msg=dict(repo=self.id,
                     updates=[u.title for u in self.compose.updates],
                     agent=self.agent,
                     ctype=self.ctype.value),
            force=True,
        )

        try:
            if self.resume:
                self.load_state()
            else:
                self.save_state()

            if self.compose.request is UpdateRequest.stable:
                self.perform_gating()

            self.determine_and_perform_tag_actions()

            self.update_security_bugs()

            self.expire_buildroot_overrides()
            self.remove_pending_tags()

            if not self.skip_mash:
                mash_process = self.mash()

            # Things we can do while we're mashing
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

            self._mark_status_changes()
            self.save_state(ComposeState.notifying)
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

            self._unlock_updates()

            self.check_all_karma_thresholds()
            self.obsolete_older_updates()

            self.save_state(ComposeState.success)
            self.success = True
            self.remove_state()

        except Exception:
            self.log.exception('Exception in MasherThread(%s)' % self.id)
            self.save_state()
            raise
        finally:
            self.finish(self.success)

    def check_all_karma_thresholds(self):
        """Run check_karma_thresholds() on testing Updates."""
        if self.compose.request is UpdateRequest.testing:
            self.log.info('Determing if any testing updates reached the karma '
                          'thresholds during the push')
            for update in self.compose.updates:
                try:
                    update.check_karma_thresholds(self.db, agent=u'bodhi')
                except BodhiException:
                    self.log.exception('Problem checking karma thresholds')

    def obsolete_older_updates(self):
        """Obsolete any older updates that may still be lying around."""
        self.log.info('Checking for obsolete updates')
        for update in self.compose.updates:
            update.obsolete_older_updates(self.db)

    def perform_gating(self):
        """Look for Updates that don't meet testing requirements, and eject them from the mash."""
        self.log.debug('Performing gating.')
        for update in self.compose.updates:
            result, reason = update.check_requirements(self.db, config)
            if not result:
                self.log.warn("%s failed gating: %s" % (update.title, reason))
                self.eject_from_mash(update, reason)

    def eject_from_mash(self, update, reason):
        """
        Eject the given Update from the current mash for the given human-readable reason.

        Args:
            update (bodhi.server.models.Update): The Update being ejected.
            reason (basestring): A human readable explanation for the ejection, which is used in a
                comment on the update, in a log message, and in a fedmsg.
        """
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
        notifications.publish(
            topic="update.eject",
            msg=dict(
                repo=self.id,
                update=update,
                reason=reason,
                request=self.compose.request,
                release=self.compose.release,
                agent=self.agent,
            ),
            force=True,
        )

    def init_state(self):
        """Create the mash_dir if it doesn't exist."""
        if not os.path.exists(self.mash_dir):
            self.log.info('Creating %s' % self.mash_dir)
            os.makedirs(self.mash_dir)

    def save_state(self, state=None):
        """
        Save the state of this push so it can be resumed later if necessary.

        Args:
            state (bodhi.server.models.ComposeState): If not ``None``, set the Compose's state
                attribute to the given state. Defaults to ``None``.
        """
        self.compose.checkpoints = json.dumps(self._checkpoints).decode('utf-8')
        if state is not None:
            self.compose.state = state
        self.db.commit()
        self.log.info('Compose object updated.')

    def load_state(self):
        """Load the state of this push so it can be resumed later if necessary."""
        self._checkpoints = json.loads(self.compose.checkpoints)
        self.log.info('Masher state loaded from %s', self.compose)
        self.log.info(self.compose.state)
        if 'completed_repo' in self._checkpoints:
            self.path = self._checkpoints['completed_repo']
            self.log.info('Resuming push with completed repo: %s' % self.path)
            return
        self.log.info('Resuming push without any completed repos')

    def remove_state(self):
        """Remove the mash lock file."""
        self.log.info('Removing state: %s', self.compose)
        self.db.delete(self.compose)

    def finish(self, success):
        """
        Clean up pungi configs if the mash was successful, and send logs and fedmsgs.

        Args:
            success (bool): True if the mash had been successful, False otherwise.
        """
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
        """Update the bug titles for security updates."""
        self.log.info('Updating bug titles for security updates')
        for update in self.compose.updates:
            if update.type is UpdateType.security:
                for bug in update.bugs:
                    bug.update_details()

    @checkpoint
    def determine_and_perform_tag_actions(self):
        """Call _determine_tag_actions() and _perform_tag_actions()."""
        self._determine_tag_actions()
        self._perform_tag_actions()

    def _determine_tag_actions(self):
        tag_types, tag_rels = Release.get_tags(self.db)
        # sync & async tagging batches
        for i, batch in enumerate(sorted_updates(self.compose.updates)):
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
        """Expire any buildroot overrides that are in this push."""
        for update in self.compose.updates:
            if update.request is UpdateRequest.stable:
                for build in update.builds:
                    if build.override:
                        try:
                            build.override.expire()
                        except Exception:
                            log.exception('Problem expiring override')

    def remove_pending_tags(self):
        """Remove all pending tags from the updates."""
        self.log.debug("Removing pending tags from builds")
        koji = buildsys.get_session()
        koji.multicall = True
        for update in self.compose.updates:
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
        """
        Child classes should override this to place type-specific Pungi files in the config dir.

        Args:
            pungi_conf_dir (basestring): A path to the directory that Pungi's configs are being
                written to.
            template_env (jinja2.Environment): The jinja2 environment to be used while rendering the
                variants.xml template.
        raises:
            NotImplementedError: The parent class does not implement this method.
        """
        raise NotImplementedError

    def create_pungi_config(self):
        """Create a temp dir and render the Pungi config templates into the dir."""
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
        env.globals['release'] = self.compose.release
        env.globals['request'] = self.compose.request
        env.globals['updates'] = self.compose.updates

        config_template = config.get(self.pungi_template_config_key)
        template = env.get_template(config_template)

        self._pungi_conf_dir = tempfile.mkdtemp(prefix='bodhi-pungi-%s-' % self.id)

        with open(os.path.join(self._pungi_conf_dir, 'pungi.conf'), 'w') as conffile:
            conffile.write(template.render())

        self.copy_additional_pungi_files(self._pungi_conf_dir, env)

    def mash(self):
        """
        Launch the Pungi child process to "punge" the repository.

        Returns:
            subprocess.Popen: A process handle to the child Pungi process.
        Raises:
            Exception: If the child Pungi process exited with a non-0 exit code within 3 seconds.
        """
        if self.path:
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
        """
        Wait for the pungi process to exit and find the path of the repository that it produced.

        Args:
            mash_process (subprocess.Popen): The Popen handle of the running child process.
        Raises:
            Exception: If pungi's exit code is not 0, or if it is unable to find the directory that
                Pungi created.
        """
        self.save_state(ComposeState.punging)
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
        if self.compose.request is UpdateRequest.testing:
            requesttype = 'updates-testing'
        # The year here is used so that we can correctly find the latest updates mash, so that we
        # find updates-20420101.1 instead of updates-testing-20420506.5
        prefix = '%s-%d-%s-%s*' % (self.compose.release.id_prefix.title(),
                                   int(self.compose.release.version),
                                   requesttype,
                                   self._startyear)

        paths = sorted(glob.glob(os.path.join(self.mash_dir, prefix)))
        if len(paths) < 1:
            raise Exception('We were unable to find a path with prefix %s in mashdir' % prefix)
        self.log.debug('Paths: %s', paths)
        self.path = paths[-1]
        self._checkpoints['completed_repo'] = self.path

    def _mark_status_changes(self):
        """Mark each update's status as fulfilling its request."""
        self.log.info('Updating update statuses.')
        for update in self.compose.updates:
            now = datetime.utcnow()
            if update.request is UpdateRequest.testing:
                update.status = UpdateStatus.testing
                update.date_testing = now
            elif update.request is UpdateRequest.stable:
                update.status = UpdateStatus.stable
                update.date_stable = now
            update.date_pushed = now
            update.pushed = True

    def _unlock_updates(self):
        """Unlock all the updates and clear their requests."""
        self.log.info("Unlocking updates.")
        for update in self.compose.updates:
            update.request = None
            update.locked = False

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
        """Generate a testing digest message for this release."""
        self.log.info('Generating testing digest for %s' % self.compose.release.name)
        for update in self.compose.updates:
            if update.request is UpdateRequest.testing:
                self.add_to_digest(update)
        self.log.info('Testing digest generation for %s complete' % self.compose.release.name)

    def generate_updateinfo(self):
        """
        Create the updateinfo.xml file for this repository.

        Returns:
            bodhi.server.metadata.UpdateInfoMetadata: The updateinfo model that was created for this
                repository.
        """
        self.log.info('Generating updateinfo for %s' % self.compose.release.name)
        self.save_state(ComposeState.updateinfo)
        uinfo = UpdateInfoMetadata(self.compose.release, self.compose.request,
                                   self.db, self.mash_dir)
        self.log.info('Updateinfo generation for %s complete' % self.compose.release.name)
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
        """Symlink our updates repository into the staging directory."""
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
        """
        Block until our repomd.xml hits the master mirror.

        Raises:
            Exception: If no folder other than "source" was found in the mash_path.
        """
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
        """Send fedmsgs to announce completion of mashing for each update."""
        self.log.info('Sending notifications')
        try:
            agent = os.getlogin()
        except OSError:  # this can happen when building on koji
            agent = u'masher'
        for update in self.compose.updates:
            topic = u'update.complete.%s' % update.request
            notifications.publish(
                topic=topic,
                msg=dict(update=update, agent=agent),
                force=True,
            )

    @checkpoint
    def modify_bugs(self):
        """Mark bugs on each Update as modified."""
        self.log.info('Updating bugs')
        for update in self.compose.updates:
            self.log.debug('Modifying bugs for %s', update.title)
            update.modify_bugs()

    @checkpoint
    def status_comments(self):
        """Add bodhi system comments to each update."""
        self.log.info('Commenting on updates')
        for update in self.compose.updates:
            update.status_comment(self.db)

    @checkpoint
    def send_stable_announcements(self):
        """Send the stable announcement e-mails out."""
        self.log.info('Sending stable update announcements')
        for update in self.compose.updates:
            if update.request is UpdateRequest.stable:
                update.send_update_notice()

    @checkpoint
    def send_testing_digest(self):
        """Send digest mail to mailing lists."""
        self.log.info('Sending updates-testing digest')
        sechead = u'The following %s Security updates need testing:\n Age  URL\n'
        crithead = u'The following %s Critical Path updates have yet to be approved:\n Age URL\n'
        testhead = u'The following builds have been pushed to %s updates-testing\n\n'

        for prefix, content in six.iteritems(self.testing_digest):
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
            updlist = sorted(content.keys())
            for pkg in updlist:
                maildata += u'    %s\n' % pkg
            maildata += u'\nDetails about builds:\n\n'
            for nvr in updlist:
                maildata += u"\n" + self.testing_digest[prefix][nvr]

            mail.send_mail(config.get('bodhi_email'), test_list,
                           '%s updates-testing report' % prefix, maildata)

    def get_security_updates(self, release):
        """
        Return an iterable of security updates in the given release.

        Args:
            release (basestring): The long_name of a Release object, used to query for the matching
                Release model.
        Returns:
            iterable: An iterable of security Update objects from the given release.
        """
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
        release = self.compose.release.id_prefix.lower().replace('-', '_')
        request = self.compose.request.value

        # If the release has primary_arches defined in the config, we need to consider whether to
        # use the release's *alt_master_repomd setting.
        primary_arches = config.get(
            '{release}_{version}_primary_arches'.format(
                release=release, version=self.compose.release.version))
        if primary_arches and arch not in primary_arches.split():
            key = '%s_%s_alt_master_repomd'
        else:
            key = '%s_%s_master_repomd'
        key = key % (release, request)

        master_repomd = config.get(key)
        if not master_repomd:
            raise ValueError("Could not find %s in the config file" % key)

        return master_repomd % (self.compose.release.version, arch)


class RPMMasherThread(MasherThread):
    """Run Pungi with configs that produce RPM repositories (yum/dnf and OSTrees)."""

    ctype = ContentType.rpm
    pungi_template_config_key = 'pungi.conf.rpm'

    def copy_additional_pungi_files(self, pungi_conf_dir, template_env):
        """
        Generate and write the variants.xml file for this Pungi run.

        Args:
            pungi_conf_dir (basestring): A path to the directory that Pungi's configs are being
                written to.
            template_env (jinja2.Environment): The jinja2 environment to be used while rendering the
                variants.xml template.
        """
        variants_template = template_env.get_template('variants.rpm.xml.j2')

        with open(os.path.join(pungi_conf_dir, 'variants.xml'), 'w') as variantsfile:
            variantsfile.write(variants_template.render())


class ModuleMasherThread(MasherThread):
    """Run Pungi with configs that produce module repositories."""

    ctype = ContentType.module
    pungi_template_config_key = 'pungi.conf.module'

    def copy_additional_pungi_files(self, pungi_conf_dir, template_env):
        """
        Generate and write the variants.xml file for this Pungi run.

        Args:
            pungi_conf_dir (basestring): A path to the directory that Pungi's configs are being
                written to.
            template_env (jinja2.Environment): The jinja2 environment to be used while rendering the
                variants.xml template.
        """
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
        Generate a list of NSVs which should be used for pungi modular compose.

        Returns:
            list: list of NSV string which should be composed.
        """
        newest_builds = {}
        # we loop through builds so we get rid of older builds and get only
        # a dict with the newest builds
        for build in self.compose.release.builds:
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
        for update in self.compose.updates:
            for build in update.builds:
                nsv = build.nvr.rsplit('-', 1)
                ns = nsv[0]
                version = nsv[1]
                newest_builds[ns] = version

        return ["%s-%s" % (nstream, v) for nstream, v in six.iteritems(newest_builds)]
