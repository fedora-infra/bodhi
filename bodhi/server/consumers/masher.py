# -*- coding: utf-8 -*-
# Copyright © 2007-2018 Red Hat, Inc. and others.
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
import os
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime

import fedmsg.consumers
import jinja2
from six.moves import zip
from six.moves.urllib import request as urllib2
from six.moves.urllib.error import HTTPError, URLError
import six

from bodhi.server import bugs, initialize_db, log, buildsys, notifications, mail
from bodhi.server.config import config, validate_path
from bodhi.server.exceptions import BodhiException
from bodhi.server.metadata import UpdateInfoMetadata
from bodhi.server.models import (Compose, ComposeState, Update, UpdateRequest, UpdateType, Release,
                                 UpdateStatus, ReleaseState, ContentType)
from bodhi.server.scripts import clean_old_mashes
from bodhi.server.util import (copy_container, sorted_updates, sanity_check_repodata,
                               transactional_session_maker)


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
        Raises:
            ValueError: If pungi.cmd is set to a path that does not exist.
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
            log.warning('No releng_fedmsg_certname defined'
                        'Cert validation disabled')
        self.max_mashes_sem = threading.BoundedSemaphore(config.get('max_concurrent_mashes'))

        # This will ensure that the configured paths exist, and will raise ValueError if any does
        # not.
        for setting in ('pungi.cmd', 'mash_dir', 'mash_stage_dir'):
            try:
                validate_path(config[setting])
            except ValueError as e:
                raise ValueError('{} Check the {} setting.'.format(str(e), setting))

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

            return [c.__json__(composer=True) for c in composes]

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
        threads = []
        for compose in self._get_composes(body):
            self.log.info('Now starting mashes')

            masher = get_masher(ContentType.from_string(compose['content_type']))
            if not masher:
                self.log.error('Unsupported content type %s submitted for mashing. SKIPPING',
                               compose['content_type'])
                continue

            thread = masher(self.max_mashes_sem, compose, agent, self.log, self.db_factory,
                            self.mash_dir, resume)
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
    Return the correct ComposerThread subclass for content_type.

    Args:
        content_type (bodhi.server.models.EnumSymbol): The content type we seek a masher for.
    Return:
        ComposerThread or None: Either a ContainerComposerThread, RPMComposerThread, or a
            ModuleComposerThread, as appropriate, or None if no masher is found.
    """
    mashers = [ContainerComposerThread, FlatpakComposerThread,
               RPMComposerThread, ModuleComposerThread]
    for possible in mashers:
        if possible.ctype is content_type:
            return possible


class ComposerThread(threading.Thread):
    """The base class that defines common things for all composes."""

    ctype = None

    def __init__(self, max_concur_sem, compose, agent, log, db_factory, mash_dir, resume=False):
        """
        Initialize the ComposerThread.

        Args:
            max_concur_sem (threading.BoundedSemaphore): Semaphore making sure only a limited
                number of ComposerThreads run at the same time.
            compose (dict): A dictionary representation of the Compose to run, formatted like the
                output of :meth:`Compose.__json__`.
            agent (basestring): The user who is executing the mash.
            log (logging.Logger): A logger to use for this mash.
            db_factory (bodhi.server.util.TransactionalSessionMaker): A DB session to use while
                mashing.
            mash_dir (basestring): A path to a directory to generate the mash in.
            resume (bool): Whether or not we are resuming a previous failed mash. Defaults to False.
        """
        super(ComposerThread, self).__init__()
        self.db_factory = db_factory
        self.log = log
        self.agent = agent
        self.max_concur_sem = max_concur_sem
        self._compose = compose
        self.resume = resume
        self.add_tags_async = []
        self.move_tags_async = []
        self.add_tags_sync = []
        self.move_tags_sync = []
        self.testing_digest = {}
        self.success = False

    def run(self):
        """Run the thread by managing a db transaction and calling work()."""
        self.log.info('Grabbing semaphore')
        self.max_concur_sem.acquire()
        self.log.info('Acquired semaphore, starting')
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
                self.compose.error_message = six.text_type(e)
                self.save_state(ComposeState.failed)

            self.log.exception('ComposerThread failed. Transaction rolled back.')
        finally:
            self.compose = None
            self.db = None
            self.max_concur_sem.release()
            self.log.info('Released semaphore')

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
        self.skip_compose = False
        if self.compose.release.state is ReleaseState.pending \
                and self.compose.request is UpdateRequest.stable:
            self.skip_compose = True

        self.log.info('Running ComposerThread(%s)' % self.id)

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

            self._compose_updates()

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

            if config['clean_old_composes']:
                # Clean old composes
                self.save_state(ComposeState.cleaning)
                clean_old_mashes.remove_old_composes()

            self.save_state(ComposeState.success)
            self.success = True

            self.remove_state()

        except Exception:
            self.log.exception('Exception in ComposerThread(%s)' % self.id)
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
                self.log.warning("%s failed gating: %s" % (update.title, reason))
                self.eject_from_mash(update, reason)
        # We may have removed some updates from this compose above, and do we don't want future
        # reads on self.compose.updates to see those, so let's mark that attribute expired so
        # sqlalchemy will requery for the composes instead of using its cached copy.
        self.db.expire(self.compose, ['updates'])

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
        log.warning(text)
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

    def save_state(self, state=None):
        """
        Save the state of this push so it can be resumed later if necessary.

        Args:
            state (bodhi.server.models.ComposeState): If not ``None``, set the Compose's state
                attribute to the given state. Defaults to ``None``.
        """
        self.compose.checkpoints = json.dumps(self._checkpoints)
        if state is not None:
            self.compose.state = state
        self.db.commit()
        self.log.info('Compose object updated.')

    def load_state(self):
        """Load the state of this push so it can be resumed later if necessary."""
        self._checkpoints = json.loads(self.compose.checkpoints)
        self.log.info('Masher state loaded from %s', self.compose)
        self.log.info(self.compose.state)

    def remove_state(self):
        """Remove the Compose object from the database."""
        self.log.info('Removing state: %s', self.compose)
        self.db.delete(self.compose)

    def finish(self, success):
        """
        Clean up pungi configs if the mash was successful, and send logs and fedmsgs.

        Args:
            success (bool): True if the mash had been successful, False otherwise.
        """
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

                    if self.skip_compose:
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
                update.remove_tag(update.release.pending_signing_tag,
                                  koji=koji)
                update.remove_tag(update.release.pending_testing_tag,
                                  koji=koji)
        result = koji.multiCall()
        self.log.debug('remove_pending_tags koji.multiCall result = %r',
                       result)

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
                log.warning('%r undefined. Not sending updates-testing digest',
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


class ContainerComposerThread(ComposerThread):
    """Use skopeo to copy and tag container images."""

    ctype = ContentType.container

    def _compose_updates(self):
        """Use skopeo to copy images to the correct repos and tags."""
        for update in self.compose.updates:

            if update.request is UpdateRequest.stable:
                destination_tag = 'latest'
            else:
                destination_tag = 'testing'

            for build in update.builds:
                # Using None as the destination tag on the first one will default to the
                # version-release string.
                for dtag in [None, build.nvr_version, destination_tag]:
                    copy_container(build, destination_tag=dtag)


class FlatpakComposerThread(ContainerComposerThread):
    """Use skopeo to copy and tag flatpak images."""

    ctype = ContentType.flatpak


class PungiComposerThread(ComposerThread):
    """Compose update with Pungi."""

    pungi_template_config_key = None

    def __init__(self, max_concur_sem, compose, agent, log, db_factory, mash_dir, resume=False):
        """
        Initialize the ComposerThread.

        Args:
            max_concur_sem (threading.BoundedSemaphore): Semaphore making sure only a limited
                number of ComposerThreads run at the same time.
            compose (dict): A dictionary representation of the Compose to run, formatted like the
                output of :meth:`Compose.__json__`.
            agent (basestring): The user who is executing the mash.
            log (logging.Logger): A logger to use for this mash.
            db_factory (bodhi.server.util.TransactionalSessionMaker): A DB session to use while
                mashing.
            mash_dir (basestring): A path to a directory to generate the mash in.
            resume (bool): Whether or not we are resuming a previous failed mash. Defaults to False.
        """
        super(PungiComposerThread, self).__init__(max_concur_sem, compose, agent, log, db_factory,
                                                  mash_dir, resume)
        self.devnull = None
        self.mash_dir = mash_dir
        self.path = None

    def finish(self, success):
        """
        Clean up pungi configs if the mash was successful, and send logs and fedmsgs.

        Args:
            success (bool): True if the mash had been successful, False otherwise.
        """
        if hasattr(self, '_pungi_conf_dir') and os.path.exists(self._pungi_conf_dir) and success:
            # Let's clean up the pungi configs we wrote
            shutil.rmtree(self._pungi_conf_dir)

        # The superclass will handle the logs and fedmsg.
        super(PungiComposerThread, self).finish(success)

    def load_state(self):
        """Set self.path if completed_repo is found in checkpoints."""
        super(PungiComposerThread, self).load_state()
        if 'completed_repo' in self._checkpoints:
            self.path = self._checkpoints['completed_repo']
            self.log.info('Resuming push with completed repo: %s' % self.path)
            return
        self.log.info('Resuming push without any completed repos')

    def _compose_updates(self):
        """Start pungi, generate updateinfo, wait for pungi, and wait for the mirrors."""
        if not os.path.exists(self.mash_dir):
            self.log.info('Creating %s' % self.mash_dir)
            os.makedirs(self.mash_dir)

        composedone = self._checkpoints.get('compose_done')

        if not self.skip_compose and not composedone:
            pungi_process = self._punge()

        # Things we can do while Pungi is running
        self.generate_testing_digest()

        if not self.skip_compose and not composedone:
            uinfo = self._generate_updateinfo()

            self._wait_for_pungi(pungi_process)

            uinfo.insert_updateinfo(self.path)

            self._sanity_check_repo()
            self._wait_for_repo_signature()
            self._stage_repo()

            self._checkpoints['compose_done'] = True
            self.save_state()

        if not self.skip_compose:
            # Wait for the repo to hit the master mirror
            self._wait_for_sync()

    def _copy_additional_pungi_files(self, pungi_conf_dir, template_env):
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

    def _create_pungi_config(self):
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

        self._copy_additional_pungi_files(self._pungi_conf_dir, env)

    def _generate_updateinfo(self):
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

    def _get_master_repomd_url(self, arch):
        """
        Return the master repomd URL for the given arch.

        Look up the correct *_master_repomd setting in the config and use it to form the URL that
        _wait_for_sync() will use to determine when the repository has been synchronized to the
        master mirror.

        Args:
            arch (basestring): The architecture for which a URL needs to be formed.

        Returns:
            basestring: A URL on the master mirror where the repomd.xml file should be synchronized.
        """
        release = self.compose.release.id_prefix.lower().replace('-', '_')
        version = self.compose.release.version
        request = self.compose.request.value

        # First check to see if there's an override for the current version, if not, fall back.
        # This will first try fedora_28_stable_(suffix), and then fedora_stable_(suffix).
        key_prefixes = ['%s_%s_%s' % (release, version, request),
                        '%s_%s' % (release, request)]
        # If the release has primary_arches defined in the config, we need to consider whether to
        # use the release's *alt_master_repomd setting.
        primary_arches = config.get(
            '{release}_{version}_primary_arches'.format(
                release=release, version=self.compose.release.version))
        if primary_arches and arch not in primary_arches.split():
            suffix = '_alt_master_repomd'
        else:
            suffix = '_master_repomd'

        keys = [key_prefix + suffix for key_prefix in key_prefixes]

        for key in keys:
            val = config.get(key)
            if val:
                return val % (version, arch)
        raise ValueError("Could not find any of %s in the config file" % ','.join(keys))

    def _punge(self):
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

        self._create_pungi_config()
        config_file = os.path.join(self._pungi_conf_dir, 'pungi.conf')
        self._label = '%s-%s' % (config.get('pungi.labeltype'),
                                 datetime.utcnow().strftime('%Y%m%d.%H%M'))
        pungi_cmd = [config.get('pungi.cmd'),
                     '--config', config_file,
                     '--quiet',
                     '--print-output-dir',
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
                                        # Pungi will log the output compose dir to stdout
                                        stdout=subprocess.PIPE,
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

        return mash_process

    def _toss_out_repo(self):
        """Remove a repo from the completed_repo checkpoint.

        This makes sure that on a next run, we redo the compose.
        """
        del self._checkpoints['completed_repo']
        self.save_state()

    def _sanity_check_repo(self):
        """Sanity check our repo.

            - make sure we didn't compose a repo full of symlinks
            - sanity check our repodata

        This basically checks that pungi was run with gather_method='hardlink-or-copy' so that
        we get a repository with either hardlinks or copied files.
        This means that we when we go and sync generated repositories out, we do not need to take
        special case to copy the target files rather than symlinks.
        """
        self.log.info("Running sanity checks on %s" % self.path)

        try:
            arches = os.listdir(os.path.join(self.path, 'compose', 'Everything'))
        except Exception:
            self.log.exception('Empty compose folder? Compose thrown out')
            self._toss_out_repo()
            raise

        if len(arches) == 0:
            self.log.error('Empty compose, compose thrown out')
            self._toss_out_repo()
            raise Exception('Empty compose found')

        for arch in arches:
            # sanity check our repodata
            try:
                if arch == 'source':
                    repodata = os.path.join(self.path, 'compose',
                                            'Everything', arch, 'tree', 'repodata')
                    sanity_check_repodata(repodata, repo_type='source')
                else:
                    repodata = os.path.join(self.path, 'compose',
                                            'Everything', arch, 'os', 'repodata')
                    repo_type = 'module' if self.ctype == ContentType.module else 'yum'
                    sanity_check_repodata(repodata, repo_type=repo_type)
            except Exception:
                self.log.exception("Repodata sanity check failed, compose thrown out")
                self._toss_out_repo()
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
                self.log.exception('Unable to check pungi mashed repositories, compose thrown out')
                self._toss_out_repo()
                raise

        return True

    def _stage_repo(self):
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

    def _wait_for_pungi(self, pungi_process):
        """
        Wait for the pungi process to exit and find the path of the repository that it produced.

        Args:
            pungi_process (subprocess.Popen): The Popen handle of the running child process.
        Raises:
            Exception: If pungi's exit code is not 0, or if it is unable to find the directory that
                Pungi created.
        """
        self.save_state(ComposeState.punging)
        if pungi_process is None:
            self.log.info('Not waiting for pungi process, as there was no pungi')
            return
        self.log.info('Waiting for pungi process to finish')
        out, err = pungi_process.communicate()
        out = out.decode()
        err = err.decode()
        self.devnull.close()
        if pungi_process.returncode != 0:
            self.log.error('Pungi exited with exit code %d', pungi_process.returncode)
            self.log.error('Stderr: %s', err)
            raise Exception('Pungi exited with status %d' % pungi_process.returncode)
        else:
            self.log.info('Pungi finished')

        # Find the path Pungi just created
        prefix = 'Compose dir: '
        for line in out.split('\n'):
            if line.startswith(prefix):
                self.path = line[len(prefix):]
        if not self.path:
            self.log.error('Stdout: %s', out)
            raise Exception('Unable to find the path to the compose')
        if not os.path.exists(os.path.join(self.path, 'compose', 'metadata', 'composeinfo.json')):
            raise Exception('Directory at %s does not look like a compose' % self.path)

        self.log.debug('Path: %s', self.path)
        self._checkpoints['completed_repo'] = self.path

    def _wait_for_repo_signature(self):
        """Wait for a repo signature to appear."""
        # This message indicates to consumers that the repos are fully created and ready to be
        # signed or otherwise processed.
        notifications.publish(
            topic="repo.done",
            msg=dict(repo=self.id, agent=self.agent, path=self.path),
            force=True,
        )
        if config.get('wait_for_repo_sig'):
            self.save_state(ComposeState.signing_repo)
            sigpaths = []
            repopath = os.path.join(self.path, 'compose', 'Everything')
            for arch in os.listdir(repopath):
                if arch == 'source':
                    sigpaths.append(os.path.join(repopath, arch, 'tree', 'repodata',
                                                 'repomd.xml.asc'))
                else:
                    sigpaths.append(os.path.join(repopath, arch, 'os', 'repodata',
                                                 'repomd.xml.asc'))

            self.log.info('Waiting for signatures in %s', ', '.join(sigpaths))
            while True:
                missing = []
                for path in sigpaths:
                    if not os.path.exists(path):
                        missing.append(path)
                if len(missing) == 0:
                    self.log.info('All signatures were created')
                    break
                else:
                    self.log.info('Waiting on %s', ', '.join(missing))
                    time.sleep(300)
        else:
            self.log.info('Not waiting for a repo signature')

    def _wait_for_sync(self):
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
            raise Exception('Not found an arch to _wait_for_sync with')

        repomd = os.path.join(mash_path, arch, 'os', 'repodata', 'repomd.xml')
        if not os.path.exists(repomd):
            self.log.error('Cannot find local repomd: %s', repomd)
            return

        self.save_state(ComposeState.syncing_repo)
        master_repomd_url = self._get_master_repomd_url(arch)

        with open(repomd) as repomdf:
            checksum = hashlib.sha1(repomdf.read().encode('utf-8')).hexdigest()
        while True:
            try:
                self.log.info('Polling %s' % master_repomd_url)
                masterrepomd = urllib2.urlopen(master_repomd_url)
            except (URLError, HTTPError):
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


class RPMComposerThread(PungiComposerThread):
    """Run Pungi with configs that produce RPM repositories (yum/dnf and OSTrees)."""

    ctype = ContentType.rpm
    pungi_template_config_key = 'pungi.conf.rpm'

    def _copy_additional_pungi_files(self, pungi_conf_dir, template_env):
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


class ModuleComposerThread(PungiComposerThread):
    """Run Pungi with configs that produce module repositories."""

    ctype = ContentType.module
    pungi_template_config_key = 'pungi.conf.module'

    def _copy_additional_pungi_files(self, pungi_conf_dir, template_env):
        """
        Generate and write the variants.xml file for this Pungi run.

        Args:
            pungi_conf_dir (basestring): A path to the directory that Pungi's configs are being
                written to.
            template_env (jinja2.Environment): The jinja2 environment to be used while rendering the
                variants.xml template.
        """
        template = template_env.get_template('variants.module.xml.j2')

        # These are assigned to self to be testable
        self._module_defs = self._generate_module_list()
        # This is so as to not break existing Pungi configurations, but ideally they get updated.
        self._module_list = ['%(name)s:%(stream)s:%(version)s' % mod for mod in self._module_defs]

        with open(os.path.join(pungi_conf_dir, 'module-variants.xml'), 'w') as variantsfile:
            self._variants_file = template.render(modules=self._module_list,
                                                  moduledefs=self._module_defs)
            variantsfile.write(self._variants_file)

    def generate_testing_digest(self):
        """Temporarily disable testing digests for modules.

        At some point, we'd want to fill the testing digest for modules too, but we basically
        need to determine what kind of emails we want to send and write templates.
        For now, let's skip this, since the current version tries to read RPM headers, which
        do not exist in the module build objects.
        """
        pass

    def _raise_on_get_build_multicall_error(self, result, build):
        """
        Raise an Exception if multicall result contains an error element.

        Args:
            result (list): Child list from the koji.multiCall() result.
            build (bodhi.server.models.Build): build for which the koji.multiCall() returned
                this result.
        """
        if type(result) == list and not result:
            err = 'Empty list returned for getBuild("%s").' % build.nvr
            self.log.error(err)
            raise Exception(err)
        elif type(result) != list:
            err = 'Unexpected data returned for getBuild("%s"): %r.' \
                % (build.nvr, result)
            self.log.error(err)
            raise Exception(err)

    def _add_build_to_newest_builds(self, newest_builds, koji_build, override=False):
        """
        Add Koji build to newest_builds dict if it's newer than the one there or override is set.

        Args:
            newest_builds (dict): Dict with name:stream as a key and moduledef as value
                (see _generate_module_list).
            koji_build (dict): Koji build to add obtained by koji.getBuild(...) method.
            override (bool): When False, the koji_build is added to newest_builds only
                if it is newer than the one currently stored in newest_builds for given
                name:stream. When True, koji_build is added to newest_build even it is
                not newer than the one currently stored there.
        """
        # name:stream:version(.context) maps to Koji's name-version-release.
        ns = "%s:%s" % (koji_build["name"], koji_build["version"])
        version = koji_build["release"]
        context = ''
        if '.' in version:
            version, context = version.split('.', 1)

        moduledef = {'name': koji_build['name'],
                     'stream': koji_build['version'],
                     'version': version,
                     'context': context}

        if ns in newest_builds and not override:
            curr_version = newest_builds[ns]['version']
            if int(curr_version) < int(version):
                newest_builds[ns] = moduledef
        else:
            newest_builds[ns] = moduledef

    def _generate_module_list(self):
        """
        Generate a list of modules which should be used for pungi modular compose.

        Returns:
            list: list of moduledef dicts with name, stream, version and context
        """
        # For modules, both name and version can contain dashes. This makes it
        # impossible to distinguish between name and version from "nvr". We
        # therefore have to ask for Koji build here and get that information
        # from there.
        koji = buildsys.get_session()
        koji.multicall = True
        for build in self.compose.release.builds:
            koji.getBuild(build.nvr)
        results = koji.multiCall()

        # we loop through builds so we get rid of older builds and get only
        # a dict with the newest builds
        newest_builds = {}
        for result, build in zip(results, self.compose.release.builds):
            self._raise_on_get_build_multicall_error(result, build)
            koji_build = result[0]
            self._add_build_to_newest_builds(newest_builds, koji_build)

        # make sure that the modules we want to update get their correct versions
        for update in self.compose.updates:
            # We need to get the Koji builds also for the updates.
            koji.multicall = True
            for update in self.compose.updates:
                for build in update.builds:
                    koji.getBuild(build.nvr)
            results = koji.multiCall()
            for result, build in zip(results, update.builds):
                self._raise_on_get_build_multicall_error(result, build)
                koji_build = result[0]
                self._add_build_to_newest_builds(newest_builds, koji_build, True)

        # The keys are just used for easy name-stream finding. The name and stream are already in
        # the module definitions.
        return newest_builds.values()
