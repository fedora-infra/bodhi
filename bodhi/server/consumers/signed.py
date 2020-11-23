# Copyright © 2016-2019 Red Hat, Inc.
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
The "signed handler".

This module is responsible for marking builds as "signed" when they get moved
from the pending-signing to pending-updates-testing tag by RoboSignatory.
"""

import logging

import fedora_messaging
from sqlalchemy import func

from bodhi.server.config import config
from bodhi.server.models import Build, UpdateRequest, UpdateStatus, TestGatingStatus
from bodhi.server.util import transactional_session_maker

log = logging.getLogger('bodhi')


class SignedHandler(object):
    """
    The Bodhi Signed Handler.

    A fedora-messaging listener waiting for messages from koji about builds being tagged.
    """

    def __init__(self):
        """Initialize the SignedHandler."""
        self.db_factory = transactional_session_maker()

    def __call__(self, message: fedora_messaging.api.Message):
        """
        Handle messages arriving with the configured topic.

        This marks a build as signed if it is assigned to the pending testing release tag.

        Example message format::
            {
                'body': {
                    'build_id': 442562,
                    'name': 'colord',
                    'tag_id': 214,
                    'instance': 's390',
                    'tag': 'f26-updates-testing-pending',
                    'user': 'sharkcz',
                    'version': '1.3.4',
                    'owner': 'sharkcz',
                    'release': '1.fc26'
                },
            }

        The message can contain additional keys.

        Duplicate messages: this method is idempotent.

        Args:
            message: The incoming message in the format described above.
        """
        message = message.body
        build_nvr = '%(name)s-%(version)s-%(release)s' % message
        tag = message['tag']

        log.info("%s tagged into %s" % (build_nvr, tag))

        with self.db_factory() as dbsession:
            build = Build.get(build_nvr)
            if not build:
                log.info("Build was not submitted, skipping")
                return

            if not build.release:
                log.info('Build is not assigned to release, skipping')
                return

            if build.update \
                    and build.update.from_tag \
                    and not build.update.release.composed_by_bodhi:
                koji_testing_tag = build.release.get_pending_testing_side_tag(build.update.from_tag)
                if tag != koji_testing_tag:
                    log.info("Tag is not testing side tag, skipping")
                    return
            elif build.release.pending_testing_tag != tag:
                log.info("Tag is not pending_testing tag, skipping")
                return

            if build.signed:
                log.info("Build was already marked as signed (maybe a duplicate message)")
                return

            # This build was moved into the pending_testing tag for the applicable release, which
            # is done by RoboSignatory to indicate that the build has been correctly signed and
            # written out. Mark it as such.
            log.info("Build has been signed, marking")
            build.signed = True
            dbsession.flush()
            log.info("Build %s has been marked as signed" % build_nvr)

            # Finally, set request to testing for non-rawhide side-tag updates
            if build.update \
                    and build.update.release.composed_by_bodhi \
                    and build.update.from_tag \
                    and build.update.signed:
                log.info(f"Setting request for new side-tag update {build.update.alias}.")
                req = UpdateRequest.testing
                build.update.set_request(dbsession, req, 'bodhi')
                return

            # For rawhide updates, if every build in update is signed change status to testing
            if build.update \
                    and not build.update.release.composed_by_bodhi \
                    and build.update.signed:
                log.info("Every build in update is signed, set status to testing")

                build.update.status = UpdateStatus.testing
                build.update.date_testing = func.current_timestamp()
                build.update.request = None
                build.update.pushed = True

                if config.get("test_gating.required"):
                    log.debug('Test gating is required, marking the update as waiting on test '
                              'gating and updating it from Greenwave to get the real status.')
                    build.update.test_gating_status = TestGatingStatus.waiting
                    build.update.update_test_gating_status()

                log.info(f"Update {build.update.alias} status has been set to testing")
