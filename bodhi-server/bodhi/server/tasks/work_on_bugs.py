# Copyright © 2019-2020 Red Hat, Inc.
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Iterate the list of bugs, retrieving information from Bugzilla and modifying them."""

import logging
import typing

from bodhi.server import util, bugs as bug_module
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException, ExternalCallException


log = logging.getLogger(__name__)


def main(alias: str, bugs: typing.List[int]):
    """
    Iterate the list of bugs, retrieving information from Bugzilla and modifying them.

    Iterate the given list of bugs associated with the given update. For each bug, retrieve
    details from Bugzilla, comment on the bug to let watchers know about the update, and mark
    the bug as MODIFIED. If the bug is a security issue, mark the update as a security update.

    Args:
        update: The update that the bugs are associated with.
        bugs: A list of bodhi.server.models.Bug instances that we wish to act on.
    """
    from bodhi.server.models import Bug, Update, UpdateType

    log.info(f'Got {len(bugs)} bugs to sync for {alias}')

    db_factory = util.transactional_session_maker()
    with db_factory() as session:
        update = Update.get(alias)
        if not update:
            raise BodhiException(f"Couldn't find alias {alias} in DB")

        for bug_id in bugs:
            bug = Bug.get(bug_id)
            # Sanity check
            if bug is None or bug not in update.bugs:
                update_bugs_ids = [b.bug_id for b in update.bugs]
                update.update_bugs(update_bugs_ids + [bug_id], session)
                # Now, after update.update_bugs, bug with bug_id should exists in DB
                bug = Bug.get(bug_id)

            log.info(f'Getting RHBZ bug {bug.bug_id}')
            try:
                rhbz_bug = bug_module.bugtracker.getbug(bug.bug_id)

                log.info(f'Updating our details for {bug.bug_id}')
                bug.update_details(rhbz_bug)
                log.info(f'  Got title {bug.title} for {bug.bug_id}')

                # If you set the type of your update to 'enhancement' but you
                # attach a security bug, we automatically change the type of your
                # update to 'security'. We need to do this first, so we don't
                # accidentally comment on stuff that we shouldn't.
                if not update.type == UpdateType.security and bug.security:
                    log.info("Setting our UpdateType to security.")
                    update.type = UpdateType.security

                log.info(f'Commenting on {bug.bug_id}')
                comment = config['initial_bug_msg'] % (
                    update.alias, update.release.long_name, update.abs_url())

                log.info(f'Modifying {bug.bug_id}')
                bug.modified(update, comment)
            except Exception:
                log.warning('Error occurred during updating single bug', exc_info=True)
                raise ExternalCallException
