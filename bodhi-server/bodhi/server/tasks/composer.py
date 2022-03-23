# Copyright © 2007-2019 Red Hat, Inc. and others.
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
The Bodhi "Composer".

This module is responsible for the process of "pushing" updates out. It's
comprised of a fedora messaging consumer that launches threads for each repository being
composed.
"""

from datetime import datetime
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import functools
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import typing

import jinja2
import sqlalchemy.orm.exc

from bodhi.messages.schemas import compose as compose_schemas
from bodhi.messages.schemas import update as update_schemas
from bodhi.server import buildsys, mail, notifications
from bodhi.server.config import config, validate_path
from bodhi.server.exceptions import BodhiException
from bodhi.server.metadata import UpdateInfoMetadata
from bodhi.server.models import (
    Compose,
    ComposeState,
    ContentType,
    Release,
    ReleaseState,
    Update,
    UpdateRequest,
    UpdateStatus,
    UpdateType,
)
from bodhi.server.tasks.clean_old_composes import main as clean_old_composes
from bodhi.server.util import (
    copy_container,
    sanity_check_repodata,
    sorted_updates,
    transactional_session_maker,
)


log = logging.getLogger('bodhi')


def checkpoint(method):
    """
    Decorate a method for skipping sections of the compose when resuming.

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


class ComposerHandler(object):
    """
    The Bodhi Composer.

    A consumer that listens for messages from releng members.

    An updates "compose" consists of:

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
    - Send messages
    - compose

    Things to do while we're waiting on compose:

    - Add testing updates to updates-testing digest
    - Generate/update updateinfo.xml
    - Have a coffee. Have 7 coffees.

    Once compose is done:

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

    def __init__(
            self, db_factory: typing.Union[transactional_session_maker, None] = None,
            compose_dir: str = config.get('compose_dir')):
        """
        Initialize the Composer.

        Args:
            db_factory (bodhi.server.util.TransactionalSessionMaker or None): If given, used as the
                db_factory for this Composer. If None (the default), a new TransactionalSessionMaker
                is created and used.
            compose_dir (str): The directory in which to place composes.
        Raises:
            ValueError: If pungi.cmd is set to a path that does not exist.
        """
        if not db_factory:
            self.db_factory = transactional_session_maker()
        else:
            self.db_factory = db_factory

        self.compose_dir = compose_dir

        self.max_composes_sem = threading.BoundedSemaphore(config.get('max_concurrent_composes'))

        # This will ensure that the configured paths exist, and will raise ValueError if any does
        # not.
        for setting in ('pungi.cmd', 'compose_dir', 'compose_stage_dir'):
            try:
                validate_path(config[setting])
            except ValueError as e:
                raise ValueError('{} Check the {} setting.'.format(str(e), setting))

    def run(self, api_version: int, data: dict):
        """
        Begin the push process.

        Here we organize & prioritize the updates, and fire off separate
        threads for each repo tag being composed.

        If there are any security updates in the push, then those repositories
        will be executed before all others.

        Args:
            api_version: API version number.
            data: Information about the compose job we are processing.
        """
        resume = data.get('resume', False)
        agent = data.get('agent')
        notifications.publish(
            compose_schemas.ComposeStartV1.from_dict(dict(agent=agent)),
            force=True)

        results = []
        threads = []
        for compose in self._get_composes(api_version, data):
            log.info('Now starting composes')

            composer = get_composer(ContentType.from_string(compose['content_type']))
            if not composer:
                log.error(
                    'Unsupported content type %s submitted for composing. SKIPPING',
                    compose['content_type']
                )
                continue

            thread = composer(self.max_composes_sem, compose, agent, self.db_factory,
                              self.compose_dir, resume)
            threads.append(thread)
            thread.start()

        log.info('All of the batches are running. Now waiting for the final results')
        for thread in threads:
            thread.join()
            for result in thread.results():
                results.append(result)

        log.info('Push complete!  Summary follows:')
        for result in results:
            log.info(result)

    def _get_composes(self, api_version: int, data: dict):
        """
        Return a list of dictionaries that represent the :class:`Composes <Compose>` we should run.

        This method is compatible with the unversioned composer.start message, and also version 2.
        If no version is found, it will use the updates listed in the message to create new Compose
        objects and return dictionary representations of them.

        This method also marks the Composes as pending, which acknowledges the receipt of the
        message.

        Args:
            data: Information about the compose job we are processing.
        Returns:
            list: A list of dictionaries, as returned from :meth:`Compose.__json__`.
        """
        with self.db_factory() as db:
            if api_version == 2:
                try:
                    composes = [Compose.from_dict(db, c) for c in data['composes']]
                except sqlalchemy.orm.exc.NoResultFound:
                    # It is possible for messages to get into our queue that reference Composes that
                    # no longer exist. If this happens, we really just want to ignore the message so
                    # that it gets dropped. In particular, we do not want to raise an Exception when
                    # this happens, because that will Nack the message put it back into the queue,
                    # resulting in a Nack loop.
                    # See https://github.com/fedora-infra/bodhi/issues/3318
                    log.info('Ignoring a compose task that references non-existing Composes')
                    return []
            else:
                raise ValueError('Unable to process request: {}'.format(data))

            # Filter out composes that are pending or have started, for example in
            # case of duplicate messages.
            composes = [c for c in composes if c.state == ComposeState.requested]

            for c in composes:
                # Acknowledge that we've received the command to run these composes.
                c.state = ComposeState.pending

            return [c.__json__(composer=True) for c in composes]


def get_composer(content_type):
    """
    Return the correct ComposerThread subclass for content_type.

    Args:
        content_type (bodhi.server.models.EnumSymbol): The content type we seek a composer for.
    Return:
        ComposerThread or None: Either a ContainerComposerThread, RPMComposerThread, or a
            ModuleComposerThread, as appropriate, or None if no composer is found.
    """
    composers = [ContainerComposerThread, FlatpakComposerThread,
                 RPMComposerThread, ModuleComposerThread]
    for possible in composers:
        if possible.ctype is content_type:
            return possible


class ComposerThread(threading.Thread):
    """The base class that defines common things for all composes."""

    ctype = None
    keep_old_composes = 10

    def __init__(self, max_concur_sem, compose, agent, db_factory, compose_dir, resume=False):
        """
        Initialize the ComposerThread.

        Args:
            max_concur_sem (threading.BoundedSemaphore): Semaphore making sure only a limited
                number of ComposerThreads run at the same time.
            compose (dict): A dictionary representation of the Compose to run, formatted like the
                output of :meth:`Compose.__json__`.
            agent (str): The user who is executing the compose.
            log (logging.Logger): A logger to use for this compose.
            db_factory (bodhi.server.util.TransactionalSessionMaker): A DB session to use while
                composing.
            compose_dir (str): A path to a directory to generate the compose in.
            resume (bool): Whether or not we are resuming a previous failed compose. Defaults to
                False.
        """
        super(ComposerThread, self).__init__()
        self.db_factory = db_factory
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
        log.info('Grabbing semaphore')
        self.max_concur_sem.acquire()
        log.info('Acquired semaphore, starting')
        try:
            with self.db_factory() as session:
                self.db = session
                self.compose = Compose.from_dict(session, self._compose)
                self._checkpoints = json.loads(self.compose.checkpoints)
                log.info('Starting composer type %s for %s with %d updates',
                         self, str(self.compose), len(self.compose.updates))
                self.save_state(ComposeState.initializing)
                self.work()
        except Exception as e:
            with self.db_factory() as session:
                self.db = session
                self.compose = Compose.from_dict(session, self._compose)
                self.compose.error_message = str(e)
                self.save_state(ComposeState.failed)

            log.exception('ComposerThread failed. Transaction rolled back.')
        finally:
            self.compose = None
            self.db = None
            self.max_concur_sem.release()
            log.info('Released semaphore')

    def results(self):
        """
        Yield log string messages about the results of this compose run.

        Yields:
            str: A string for human readers indicating the success of the compose.
        """
        attrs = ['name', 'success']
        yield "  name:  %(name)-20s  success:  %(success)s" % dict(
            zip(attrs, [getattr(self, attr, 'Undefined') for attr in attrs])
        )

    def work(self):
        """Perform the various high-level tasks for the compose."""
        self.id = getattr(self.compose.release, '%s_tag' % self.compose.request.value)

        # Set our thread's "name" so it shows up nicely in the logs.
        # https://docs.python.org/2/library/threading.html#thread-objects
        self.name = self.id

        # For 'pending' branched releases, we only want to perform repo-related
        # tasks for testing updates. For stable updates, we should just add the
        # dist_tag and do everything else other than composing/updateinfo, since
        # the nightly build-branched cron job composes for us.
        self.skip_compose = False
        if self.compose.release.state is ReleaseState.pending \
                and self.compose.request is UpdateRequest.stable:
            self.skip_compose = True

        log.info('Running ComposerThread(%s)' % self.id)

        notifications.publish(compose_schemas.ComposeComposingV1.from_dict(
            dict(repo=self.id,
                 updates=[' '.join([b.nvr for b in u.builds]) for u in self.compose.updates],
                 agent=self.agent,
                 ctype=self.ctype.value)),
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
                clean_old_composes(self.keep_old_composes)

            self.save_state(ComposeState.success)
            self.success = True

            self.remove_state()

        except Exception:
            log.exception('Exception in ComposerThread(%s)' % self.id)
            self.save_state()
            raise
        finally:
            self.finish(self.success)

    def check_all_karma_thresholds(self):
        """Run check_karma_thresholds() on testing Updates."""
        if self.compose.request is UpdateRequest.testing:
            log.info('Determine if any testing updates reached the karma '
                     'thresholds during the push')
            for update in self.compose.updates:
                try:
                    update.check_karma_thresholds(self.db, agent='bodhi')
                except BodhiException:
                    log.exception('Problem checking karma thresholds')

    def obsolete_older_updates(self):
        """Obsolete any older updates that may still be lying around."""
        log.info('Checking for obsolete updates')
        for update in self.compose.updates:
            update.obsolete_older_updates(self.db)

    def perform_gating(self):
        """Eject Updates that don't meet testing requirements from the compose."""
        log.debug('Performing gating.')
        for update in self.compose.updates:
            result, reason = update.check_requirements(self.db, config)
            if not result:
                log.warning("%s failed gating: %s" % (update.alias, reason))
                self.eject_from_compose(update, reason)
        # We may have removed some updates from this compose above, and do we don't want future
        # reads on self.compose.updates to see those, so let's mark that attribute expired so
        # sqlalchemy will requery for the composes instead of using its cached copy.
        self.db.expire(self.compose, ['updates'])

    def eject_from_compose(self, update, reason):
        """
        Eject the given Update from the current compose for the given human-readable reason.

        Args:
            update (bodhi.server.models.Update): The Update being ejected.
            reason (str): A human readable explanation for the ejection, which is used in a
                comment on the update, in a log message, and in a bus message.
        """
        update.locked = False
        text = '%s ejected from the push because %r' % (update.alias, reason)
        log.warning(text)
        update.comment(self.db, text, author='bodhi')
        # Remove the pending tag as well
        if update.request is UpdateRequest.stable:
            update.remove_tag(update.release.pending_stable_tag,
                              koji=buildsys.get_session())
        elif update.request is UpdateRequest.testing:
            update.remove_tag(update.release.pending_testing_tag,
                              koji=buildsys.get_session())
        update.request = None
        notifications.publish(
            update_schemas.UpdateEjectV1.from_dict(
                dict(
                    repo=self.id,
                    update=update,
                    reason=reason,
                    request=self.compose.request,
                    release=self.compose.release,
                    agent=self.agent,
                )),
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
        log.info('Compose object updated.')

    def load_state(self):
        """Load the state of this push so it can be resumed later if necessary."""
        self._checkpoints = json.loads(self.compose.checkpoints)
        log.info('Composer state loaded from %s', self.compose)
        log.info(self.compose.state)

    def remove_state(self):
        """Remove the Compose object from the database."""
        log.info('Removing state: %s', self.compose)
        self.db.delete(self.compose)

    def finish(self, success):
        """
        Clean up pungi configs if the compose was successful, and send logs and bus messages.

        Args:
            success (bool): True if the compose had been successful, False otherwise.
        """
        log.info('Thread(%s) finished.  Success: %r' % (self.id, success))
        notifications.publish(compose_schemas.ComposeCompleteV1.from_dict(dict(
            dict(success=success, repo=self.id, agent=self.agent, ctype=self.ctype.value))),
            force=True,
        )

    def update_security_bugs(self):
        """Update the bug titles for security updates."""
        log.info('Updating bug titles for security updates')
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
                        self.eject_from_compose(update, reason)
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
                log.info("Adding tag %s to %s" % (tag, build))
                koji.tagBuild(tag, build, force=True)
            for action in move:
                from_tag, to_tag, build = action
                log.info('Moving %s from %s to %s' % (build, from_tag, to_tag))
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
                            log.debug(f"Expiring BRO for {build.nvr} because it is being pushed.")
                            build.override.expire()
                        except Exception:
                            log.exception('Problem expiring override')

    def remove_pending_tags(self):
        """Remove all pending tags from the updates."""
        log.debug("Removing pending tags from builds")
        koji = buildsys.get_session()
        koji.multicall = True
        for update in self.compose.updates:
            if update.request is UpdateRequest.stable:
                update.remove_tag(update.release.pending_stable_tag,
                                  koji=koji)
                if update.from_tag:
                    # Remove the side-tag so that Koji gc can delete it if empty
                    update.remove_tag(update.from_tag, koji=koji)
            elif update.request is UpdateRequest.testing:
                update.remove_tag(update.release.pending_signing_tag,
                                  koji=koji)
                update.remove_tag(update.release.pending_testing_tag,
                                  koji=koji)
        result = koji.multiCall()
        log.debug('remove_pending_tags koji.multiCall result = %r', result)

    def _mark_status_changes(self):
        """Mark each update's status as fulfilling its request."""
        eol_sidetags = []
        log.info('Updating update statuses.')
        for update in self.compose.updates:
            now = datetime.utcnow()
            if update.request is UpdateRequest.testing:
                update.status = UpdateStatus.testing
                update.date_testing = now
            elif update.request is UpdateRequest.stable:
                update.status = UpdateStatus.stable
                update.date_stable = now
                if update.from_tag:
                    eol_sidetags.append(update.from_tag)
            update.date_pushed = now
            update.pushed = True

        log.info('Deleting EOL side-tags.')
        koji = buildsys.get_session()
        koji.multicall = True
        for sidetag in eol_sidetags:
            koji.deleteTag(sidetag)
        koji.multiCall()

    def _unlock_updates(self):
        """Unlock all the updates and clear their requests."""
        log.info("Unlocking updates.")
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
        log.info('Generating testing digest for %s' % self.compose.release.name)
        for update in self.compose.updates:
            if update.request is UpdateRequest.testing:
                self.add_to_digest(update)
        log.info('Testing digest generation for %s complete' % self.compose.release.name)

    def send_notifications(self):
        """Send messages to announce completion of composing for each update."""
        log.info('Sending notifications')
        try:
            agent = os.getlogin()
        except OSError:  # this can happen when building on koji
            agent = 'composer'
        for update in self.compose.updates:
            messages = {
                UpdateRequest.stable: update_schemas.UpdateCompleteStableV1,
                UpdateRequest.testing: update_schemas.UpdateCompleteTestingV1
            }
            message = messages[update.request].from_dict(dict(update=update, agent=agent))
            notifications.publish(message, force=True)

    @checkpoint
    def modify_bugs(self):
        """Mark bugs on each Update as modified."""
        log.info('Updating bugs')
        for update in self.compose.updates:
            log.debug('Modifying bugs for %s', update.alias)
            update.modify_bugs()

    @checkpoint
    def status_comments(self):
        """Add bodhi system comments to each update."""
        log.info('Commenting on updates')
        for update in self.compose.updates:
            update.status_comment(self.db)

    @checkpoint
    def send_stable_announcements(self):
        """Send the stable announcement e-mails out."""
        log.info('Sending stable update announcements')
        for update in self.compose.updates:
            if update.request is UpdateRequest.stable:
                update.send_update_notice()

    @checkpoint
    def send_testing_digest(self):
        """Send digest mail to mailing lists."""
        log.info('Sending updates-testing digest')
        sechead = 'The following %s Security updates need testing:\n Age  URL\n'
        crithead = 'The following %s Critical Path updates have yet to be approved:\n Age URL\n'
        testhead = 'The following builds have been pushed to %s updates-testing\n\n'

        for prefix, content in self.testing_digest.items():
            release = self.db.query(Release).filter_by(long_name=prefix).one()
            test_list_key = '%s_test_announce_list' % (
                release.id_prefix.lower().replace('-', '_'))
            test_list = config.get(test_list_key)
            if not test_list:
                log.warning('%r undefined. Not sending updates-testing digest',
                            test_list_key)
                continue

            log.debug("Sending digest for updates-testing %s" % prefix)
            maildata = ''
            security_updates = self.get_security_updates(prefix)
            if security_updates:
                maildata += sechead % prefix
                for update in security_updates:
                    maildata += ' %3i  %s   %s\n' % (
                        update.days_in_testing,
                        update.abs_url(),
                        update.title)
                maildata += '\n\n'

            critpath_updates = self.get_unapproved_critpath_updates(prefix)
            if critpath_updates:
                maildata += crithead % prefix
                for update in self.get_unapproved_critpath_updates(prefix):
                    maildata += ' %3i  %s   %s\n' % (
                        update.days_in_testing,
                        update.abs_url(),
                        update.title)
                maildata += '\n\n'

            maildata += testhead % prefix
            updlist = sorted(content.keys())
            for pkg in updlist:
                maildata += '    %s\n' % pkg
            maildata += '\nDetails about builds:\n\n'
            for nvr in updlist:
                maildata += "\n" + self.testing_digest[prefix][nvr]

            mail.send_mail(config.get('bodhi_email'), test_list,
                           '%s updates-testing report' % prefix, maildata)

    def get_security_updates(self, release):
        """
        Return an iterable of security updates in the given release.

        Args:
            release (str): The long_name of a Release object, used to query for the matching
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
            release (str): The long_name of the Release to be queried.
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
        """
        Use skopeo to copy images to the correct repos and tags.

        Raises:
            RuntimeError: If skopeo returns a non-0 exit code during copy_container.
        """
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

    def __init__(self, max_concur_sem, compose, agent, db_factory, compose_dir, resume=False):
        """
        Initialize the ComposerThread.

        Args:
            max_concur_sem (threading.BoundedSemaphore): Semaphore making sure only a limited
                number of ComposerThreads run at the same time.
            compose (dict): A dictionary representation of the Compose to run, formatted like the
                output of :meth:`Compose.__json__`.
            agent (str): The user who is executing the compose.
            log (logging.Logger): A logger to use for this compose.
            db_factory (bodhi.server.util.TransactionalSessionMaker): A DB session to use while
                composing.
            compose_dir (str): A path to a directory to generate the compose in.
            resume (bool): Whether or not we are resuming a previous failed compose. Defaults to
                False.
        """
        super(PungiComposerThread, self).__init__(max_concur_sem, compose, agent, db_factory,
                                                  compose_dir, resume)
        self.compose_dir = compose_dir
        self.path = None

    def finish(self, success):
        """
        Clean up pungi configs if the compose was successful, and send logs and messages.

        Args:
            success (bool): True if the compose had been successful, False otherwise.
        """
        if hasattr(self, '_pungi_conf_dir') and os.path.exists(self._pungi_conf_dir) and success:
            # Let's clean up the pungi configs we wrote
            shutil.rmtree(self._pungi_conf_dir)

        # The superclass will handle the logs and messages.
        super(PungiComposerThread, self).finish(success)

    def load_state(self):
        """Set self.path if completed_repo is found in checkpoints."""
        super(PungiComposerThread, self).load_state()
        if 'completed_repo' in self._checkpoints:
            self.path = self._checkpoints['completed_repo']
            log.info('Resuming push with completed repo: %s' % self.path)
            return
        log.info('Resuming push without any completed repos')

    def _compose_updates(self):
        """Start pungi, generate updateinfo, wait for pungi, and wait for the mirrors."""
        if not os.path.exists(self.compose_dir):
            log.info('Creating %s' % self.compose_dir)
            os.makedirs(self.compose_dir)

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
            pungi_conf_dir (str): A path to the directory that Pungi's configs are being
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
        log.info('Generating updateinfo for %s' % self.compose.release.name)
        self.save_state(ComposeState.updateinfo)
        uinfo = UpdateInfoMetadata(self.compose.release, self.compose.request,
                                   self.db, self.compose_dir)
        log.info('Updateinfo generation for %s complete' % self.compose.release.name)
        return uinfo

    def _get_master_repomd_url(self, arch):
        """
        Return the master repomd URL for the given arch.

        Look up the correct *_master_repomd setting in the config and use it to form the URL that
        _wait_for_sync() will use to determine when the repository has been synchronized to the
        master mirror.

        Args:
            arch (str): The architecture for which a URL needs to be formed.

        Returns:
            str: A URL on the master mirror where the repomd.xml file should be synchronized.
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
            log.info('Skipping completed repo: %s', self.path)
            return

        self._create_pungi_config()
        config_file = os.path.join(self._pungi_conf_dir, 'pungi.conf')
        self._label = '%s-%s' % (config.get('pungi.labeltype'),
                                 datetime.utcnow().strftime('%Y%m%d.%H%M'))
        pungi_cmd = [config.get('pungi.cmd'),
                     '--config', config_file,
                     '--quiet',
                     '--print-output-dir',
                     '--target-dir', self.compose_dir,
                     '--old-composes', self.compose_dir,
                     '--no-latest-link',
                     '--label', self._label]
        pungi_cmd += config.get('pungi.extracmdline')

        log.info('Running the pungi command: %s', pungi_cmd)
        compose_process = subprocess.Popen(pungi_cmd,
                                           # Nope. No shell for you
                                           shell=False,
                                           # Should be useless, but just to set something
                                           # predictable
                                           cwd=self.compose_dir,
                                           # Pungi will log the output compose dir to stdout
                                           stdout=subprocess.PIPE,
                                           # Stderr should also go to pungi.global.log if it starts
                                           stderr=subprocess.PIPE,
                                           # We will never have additional input
                                           stdin=subprocess.DEVNULL)
        log.info('Pungi running as PID: %s', compose_process.pid)
        # Since the compose process takes a long time, we can safely just wait 3 seconds
        # to abort the entire compose early if Pungi fails to start up correctly.
        time.sleep(3)
        if compose_process.poll() not in [0, None]:
            log.error('Pungi process terminated with error within 3 seconds! Abandoning!')
            _, err = compose_process.communicate()
            log.error('Stderr: %s', err)
            raise Exception('Pungi returned error, aborting!')

        return compose_process

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
        log.info("Running sanity checks on %s" % self.path)

        try:
            arches = os.listdir(os.path.join(self.path, 'compose', 'Everything'))
        except Exception:
            log.exception('Empty compose folder? Compose thrown out')
            self._toss_out_repo()
            raise

        if len(arches) == 0:
            log.error('Empty compose, compose thrown out')
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
                log.exception("Repodata sanity check failed, compose thrown out")
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
                                log.error('Pungi out directory contains at least one '
                                          'symlink at %s', checkfile)
                                raise Exception('Symlinks found')
                            # We have checked the first rpm in the subdir
                            break
            except Exception:
                log.exception('Unable to check pungi composed repositories, compose thrown out')
                self._toss_out_repo()
                raise

        return True

    def _stage_repo(self):
        """Symlink our updates repository into the staging directory."""
        stage_dir = config.get('compose_stage_dir')
        if not os.path.isdir(stage_dir):
            log.info('Creating compose_stage_dir %s', stage_dir)
            os.mkdir(stage_dir)
        link = os.path.join(stage_dir, self.id)
        if os.path.islink(link):
            os.unlink(link)
        log.info("Creating symlink: %s => %s" % (link, self.path))
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
            log.info('Not waiting for pungi process, as there was no pungi')
            return
        log.info('Waiting for pungi process to finish')
        out, err = pungi_process.communicate()
        out = out.decode()
        err = err.decode()
        if pungi_process.returncode != 0:
            log.error('Pungi exited with exit code %d', pungi_process.returncode)
            log.error('Stderr: %s', err)
            raise Exception('Pungi exited with status %d' % pungi_process.returncode)
        else:
            log.info('Pungi finished')

        # Find the path Pungi just created
        prefix = 'Compose dir: '
        for line in out.split('\n'):
            if line.startswith(prefix):
                self.path = line[len(prefix):]
        if not self.path:
            log.error('Stdout: %s', out)
            raise Exception('Unable to find the path to the compose')
        if not os.path.exists(os.path.join(self.path, 'compose', 'metadata', 'composeinfo.json')):
            raise Exception('Directory at %s does not look like a compose' % self.path)

        log.debug('Path: %s', self.path)
        self._checkpoints['completed_repo'] = self.path

    def _wait_for_repo_signature(self):
        """Wait for a repo signature to appear."""
        # This message indicates to consumers that the repos are fully created and ready to be
        # signed or otherwise processed.
        notifications.publish(compose_schemas.RepoDoneV1.from_dict(
            dict(repo=self.id, agent=self.agent, path=self.path)),
            force=True)
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

            log.info('Waiting for signatures in %s', ', '.join(sigpaths))
            while True:
                missing = []
                for path in sigpaths:
                    if not os.path.exists(path):
                        missing.append(path)
                if len(missing) == 0:
                    log.info('All signatures were created')
                    break
                else:
                    log.info('Waiting on %s', ', '.join(missing))
                    time.sleep(300)
        else:
            log.info('Not waiting for a repo signature')

    def _wait_for_sync(self):
        """
        Block until our repomd.xml hits the master mirror.

        Raises:
            Exception: If no folder other than "source" was found in the compose_path.
        """
        log.info('Waiting for updates to hit the master mirror')
        notifications.publish(compose_schemas.ComposeSyncWaitV1.from_dict(
            dict(repo=self.id, agent=self.agent)),
            force=True)
        compose_path = os.path.join(self.path, 'compose', 'Everything')
        checkarch = None
        # Find the first non-source arch to check against
        for arch in os.listdir(compose_path):
            if arch == 'source':
                continue
            checkarch = arch
            break
        if not checkarch:
            raise Exception('Not found an arch to _wait_for_sync with')

        repomd = os.path.join(compose_path, arch, 'os', 'repodata', 'repomd.xml')
        if not os.path.exists(repomd):
            log.error('Cannot find local repomd: %s', repomd)
            return

        self.save_state(ComposeState.syncing_repo)
        master_repomd_url = self._get_master_repomd_url(arch)

        with open(repomd) as repomdf:
            checksum = hashlib.sha1(repomdf.read().encode('utf-8')).hexdigest()
        while True:
            try:
                log.info('Polling %s' % master_repomd_url)
                masterrepomd = urlopen(master_repomd_url)
                newsum = hashlib.sha1(masterrepomd.read()).hexdigest()
            except (ConnectionResetError, IncompleteRead, URLError, HTTPError):
                log.exception('Error fetching repomd.xml')
                time.sleep(200)
                continue
            if newsum == checksum:
                log.info("master repomd.xml matches!")
                notifications.publish(compose_schemas.ComposeSyncDoneV1.from_dict(
                    dict(repo=self.id, agent=self.agent)),
                    force=True)
                return

            log.debug("master repomd.xml doesn't match! %s != %s for %r",
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
            pungi_conf_dir (str): A path to the directory that Pungi's configs are being
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
            pungi_conf_dir (str): A path to the directory that Pungi's configs are being
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
            log.error(err)
            raise Exception(err)
        elif type(result) != list:
            err = 'Unexpected data returned for getBuild("%s"): %r.' \
                % (build.nvr, result)
            log.error(err)
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
