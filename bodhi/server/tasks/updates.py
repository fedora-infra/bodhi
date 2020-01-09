# Copyright 2015-2019 Red Hat Inc., and others.
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
The "updates handler".

This module is responsible for doing value-added work "offline" that used to be
done when updates were submitted.  Specifically, when someone submits an update
we used to:

- Update any bugs in bugzilla associated with the update.
- Check for test cases in the wiki.

Those things could sometimes take a *very* long time, especially if there were
lots of builds and lots of bugs in the update.

Now, update-submission breezes by those steps and simply tells the user "OK".
A message gets published when their update goes through, and *that* message
gets received here and triggers us to do all that network-laden heavy lifting.
"""

import logging
import time

from sqlalchemy import func

from bodhi.server import util, bugs as bug_module
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from bodhi.server.models import Bug, Update, UpdateType, UpdateStatus


log = logging.getLogger('bodhi')


class UpdatesHandler:
    """
    Perform background tasks when updates are created or edited.

    This Celery task is run when an update is created or editied in the frontend,
    and performs background tasks such as modifying Bugzilla issues (and loading information from
    Bugzilla so we can display it to the user) and looking up wiki test cases.

    Attributes:
        db_factory (bodhi.server.util.TransactionalSessionMaker): A context manager that yields a
            database session.
        handle_bugs (bool): If True, interact with Bugzilla. Else do not.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the UpdatesHandler."""
        self.db_factory = util.transactional_session_maker()

        self.handle_bugs = bool(config.get('bodhi_email'))
        if not self.handle_bugs:
            log.warning("No bodhi_email defined; not fetching bug details")

    def run(self, api_version: int, data: dict):
        """
        Process the given message, updating relevant bugs and test cases.

        Duplicate messages: if the server delivers the message multiple times,
        the bugs and test cases are simply re-fetched and updated, so nothing
        bad happens.

        Args:
            api_version: API version number.
            data: Information about a new or edited update.
        """
        if api_version == 1:
            alias = data["update"].get("alias")
        elif api_version == 2:
            try:
                alias = data['update_alias']
            except KeyError:
                log.error(f"Wrong message format for the handle_update task: {data}")
                return
        else:
            log.error(f"The Updates Handler doesn't know how to handle api_version {api_version}. "
                      f"Message was: {data}")
            return

        action = data["action"]
        log.info("Updates Handler handling  %s, %s" % (alias, action))

        # Go to sleep for a second to try and avoid a race condition
        # https://github.com/fedora-infra/bodhi/issues/458
        time.sleep(1)

        with self.db_factory() as session:
            update = Update.get(alias)
            if not update:
                raise BodhiException("Couldn't find alias '%s' in DB" % alias)

            bugs = []
            if action == "edit":
                # If editing a Pending update, all of whose builds are signed, for a release
                # which isn't composed by Bodhi (i.e. Rawhide), move it directly to Testing.
                if not update.release.composed_by_bodhi \
                        and update.status == UpdateStatus.pending \
                        and update.signed:
                    log.info("Every build in the update is signed, set status to testing")

                    update.status = UpdateStatus.testing
                    update.date_testing = func.current_timestamp()
                    update.request = None

                    log.info(f"Update status of {update.display_name} has been set to testing")

                for idx in data['new_bugs']:
                    bug = Bug.get(idx)

                    # Sanity check
                    if bug is None or bug not in update.bugs:
                        update_bugs_ids = [b.bug_id for b in update.bugs]
                        update.update_bugs(update_bugs_ids + [idx], session)

                        # Now, after update.update_bugs, bug with idx should exists in DB
                        bug = Bug.get(idx)

                    bugs.append(bug)

            elif action == "testing":
                bugs = update.bugs
            else:
                raise NotImplementedError("Should never get here.")

            self.work_on_bugs(session, update, bugs)
            self.fetch_test_cases(session, update)

        if config['test_gating.required']:
            with self.db_factory() as session:
                update = Update.get(alias)
                update.update_test_gating_status()

        log.info("Updates Handler done with %s, %s" % (alias, action))

    def fetch_test_cases(self, session, update):
        """
        Query the wiki for test cases for each package on the given update.

        Args:
            session (sqlalchemy.orm.session.Session): A database session.
            update (bodhi.server.models.Update): The update's builds are iterated upon to find test
                cases for their associated Packages..
        """
        for build in update.builds:
            try:
                build.package.fetch_test_cases(session)
            except BodhiException:
                log.warning('Error occurred during fetching testcases', exc_info=True)

    def work_on_bugs(self, session, update, bugs):
        """
        Iterate the list of bugs, retrieving information from Bugzilla and modifying them.

        Iterate the given list of bugs associated with the given update. For each bug, retrieve
        details from Bugzilla, comment on the bug to let watchers know about the update, and mark
        the bug as MODIFIED. If the bug is a security issue, mark the update as a security update.

        If handle_bugs is not True, return and do nothing.

        Args:
            session (sqlalchemy.orm.session.Session): A database session.
            update (bodhi.server.models.Update): The update that the bugs are associated with.
            bugs (list): A list of bodhi.server.models.Bug instances that we wish to act on.
        """
        if not self.handle_bugs:
            log.warning("Not configured to handle bugs")
            return

        log.info("Got %i bugs to sync for %r" % (len(bugs), update.alias))
        for bug in bugs:
            log.info("Getting RHBZ bug %r" % bug.bug_id)
            try:
                rhbz_bug = bug_module.bugtracker.getbug(bug.bug_id)

                log.info("Updating our details for %r" % bug.bug_id)
                bug.update_details(rhbz_bug)
                log.info("  Got title %r for %r" % (bug.title, bug.bug_id))

                # If you set the type of your update to 'enhancement' but you
                # attach a security bug, we automatically change the type of your
                # update to 'security'. We need to do this first, so we don't
                # accidentally comment on stuff that we shouldn't.
                if bug.security:
                    log.info("Setting our UpdateType to security.")
                    update.type = UpdateType.security

                log.info("Commenting on %r" % bug.bug_id)
                comment = config['initial_bug_msg'] % (
                    update.alias, update.release.long_name, update.abs_url())

                log.info("Modifying %r" % bug.bug_id)
                bug.modified(update, comment)
            except Exception:
                log.warning('Error occurred during updating single bug', exc_info=True)
