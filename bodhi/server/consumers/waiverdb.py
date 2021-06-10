# Copyright Red Hat and others.
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
"""
The "waiverdb handler".

This module is responsible for listening for 'new waiver' messages from
WaiverDB, and re-checking the gating decision for the relevant update.
"""

import logging

import fedora_messaging

from bodhi.server.consumers.util import update_from_db_message
from bodhi.server.models import TestGatingStatus
from bodhi.server.util import transactional_session_maker

log = logging.getLogger(__name__)


class WaiverdbHandler:
    """
    The Bodhi WaiverDB Handler.

    A fedora-messaging listener waiting for messages from WaiverDB and
    updating gating status of the relevant update.
    """

    def __init__(self):
        """Initialize the handler."""
        self.db_factory = transactional_session_maker()

    def __call__(self, message: fedora_messaging.api.Message):
        """Handle messages arriving with the configured topic."""
        msg = message.body
        if not msg:
            log.debug("Ignoring message without body.")
            return

        subject = msg.get("subject")
        if subject is None:
            log.error(f"Couldn't find subject in WaiverDB message {message.id}")
            return

        with self.db_factory():
            # find the update
            update = update_from_db_message(message.id, subject)
            # update the gating status unless it's already "passed", a
            # waiver can't change it from passed to anything else
            if update and update.test_gating_status != TestGatingStatus.passed:
                log.info(f"Updating the test_gating_status for: {update.alias}")
                update.update_test_gating_status()
