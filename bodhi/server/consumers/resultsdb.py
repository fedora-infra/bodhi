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
The "resultsdb handler".

This module is responsible for listening for messages from ResultsDB.
If a message seems like it might be a result change for an update or
build from an update, we re-check the gating decision for that update.
"""

import logging

import fedora_messaging

from bodhi.server.consumers.util import update_from_db_message
from bodhi.server.models import TestGatingStatus
from bodhi.server.util import transactional_session_maker

log = logging.getLogger(__name__)


class ResultsdbHandler:
    """
    The Bodhi ResultsDB Handler.

    A fedora-messaging listener waiting for messages from resultsdb that may
    affect gating status for an update.
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

        passed = msg.get("outcome") in ("PASSED", "INFO")

        data = msg.get("data")
        if not data:
            log.error(f"Couldn't find data dict in ResultsDB message {message.id}")
            return

        with self.db_factory():
            # find the update
            update = update_from_db_message(message.id, msg["data"])
            if not update:
                # update_from_db_message will already have logged why
                return
            # update the gating status if there's a chance it changed
            status = update.test_gating_status
            if (
                (passed and status == TestGatingStatus.passed)
                or (not passed and status == TestGatingStatus.failed)
            ):
                log.debug("Not updating test_gating_status as no chance of a change")
                return
            log.info(f"Updating the test_gating_status for: {update.alias}")
            update.update_test_gating_status()
