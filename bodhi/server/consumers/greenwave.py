# Copyright © 2019 Red Hat, Inc.
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
The "greenwave handler".

This module is responsible for listening for messages from greenwave.
It then updates the policies of the build that greenwave checked.
"""

import logging

import fedora_messaging

from bodhi.server.models import Build, TestGatingStatus
from bodhi.server.util import transactional_session_maker

log = logging.getLogger(__name__)


class GreenwaveHandler:
    """
    The Bodhi Greenwave Handler.

    A fedora-messaging listener waiting for messages from greenwave about enforced policies.
    """

    def __init__(self):
        """Initialize the GreenwaveHandler."""
        self.db_factory = transactional_session_maker()

    def __call__(self, message: fedora_messaging.api.Message):
        """Handle messages arriving with the configured topic."""
        msg = message.body
        if not msg:
            log.debug("Ignoring message without body.")
            return

        subject_identifier = msg.get("subject_identifier")

        if subject_identifier is None:
            log.debug("Couldn't find subject_identifier in Greenwave message")
            return

        subject_type = msg.get("subject_type")
        if subject_type == "compose":
            log.debug("Not requesting a decision for a compose")
            return

        subject_identifier = msg.get("subject_identifier")

        if "policies_satisfied" not in msg:
            log.debug("Couldn't find policies_satisfied in Greenwave message")
            return

        with self.db_factory():

            build = Build.get(subject_identifier)
            if build is None:
                log.debug(f"Couldn't find build {subject_identifier} in DB")
                return

            update = build.update
            log.info(f"Updating the test_gating_status for: {update.alias}")
            if len(update.builds) > 1:
                update.update_test_gating_status()
            else:
                update.test_gating_status = self._extract_gating_status(msg)

    def _extract_gating_status(self, msg):
        """
        Extract gating information from the Greenwave message and return it.

        Returns:
            TestGatingStatus:
                - TestGatingStatus.ignored if no tests are required
                - TestGatingStatus.failed if policies are not satisfied
                - TestGatingStatus.passed if policies are satisfied, and there
                  are required tests
        """
        if not msg['policies_satisfied']:
            return TestGatingStatus.failed
        if msg['summary'] == 'no tests are required':
            # If an unrestricted policy is applied and no tests are required
            # on this update, let's set the test gating as ignored in Bodhi.
            return TestGatingStatus.ignored
        return TestGatingStatus.passed
