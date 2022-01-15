# Copyright © 2017 Red Hat, Inc.
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
Avoid Updates being stuck in pending.

It may happen that Bodhi misses fedora-messaging messages announcing builds
have been signed.
In these cases, the Update remain stuck in pending until a manual intervention.

This script will cycle through builds of Updates in pending status and update
the signed status in the db to match the tags found in Koji.
"""

import logging
from datetime import datetime, timedelta

from bodhi.server import buildsys, models
from bodhi.server.config import config
from bodhi.server.util import transactional_session_maker


log = logging.getLogger(__name__)


def main():
    """Check build tags and sign those we missed."""
    db_factory = transactional_session_maker()
    older_than = datetime.utcnow() - timedelta(days=config.get('check_signed_builds_delay'))
    with db_factory() as session:
        updates = models.Update.query.filter(
            models.Update.status == models.UpdateStatus.pending
        ).filter(
            models.Update.release_id == models.Release.id
        ).filter(
            models.Release.state.in_([
                models.ReleaseState.current,
                models.ReleaseState.pending,
                models.ReleaseState.frozen,
            ])
        ).all()

        if len(updates) == 0:
            log.debug('No stuck Updates found')
            return

        kc = buildsys.get_session()
        stuck_builds = []
        overlooked_builds = []

        for update in updates:
            # Let Bodhi have its times
            if update.date_submitted >= older_than:
                continue
            builds = update.builds
            # Clean Updates with no builds
            if len(builds) == 0:
                log.debug(f'Obsoleting empty update {update.alias}')
                update.obsolete(session)
                session.flush()
                continue
            pending_signing_tag = update.release.pending_signing_tag
            pending_testing_tag = update.release.pending_testing_tag
            for build in builds:
                if build.signed:
                    log.debug(f'{build.nvr} already marked as signed')
                    continue
                build_tags = [t['name'] for t in kc.listTags(build=build.nvr)]
                if pending_signing_tag not in build_tags and pending_testing_tag in build_tags:
                    # Our composer missed the message that the build got signed
                    log.debug(f'Changing signed status of {build.nvr}')
                    build.signed = True
                elif pending_signing_tag in build_tags and pending_testing_tag not in build_tags:
                    # autosign missed the message that the build is waiting to be signed
                    log.debug(f'{build.nvr} is stuck waiting to be signed, let\'s try again')
                    stuck_builds.append(build.nvr)
                elif (pending_signing_tag not in build_tags
                      and pending_testing_tag not in build_tags):
                    # this means that an update has been created but we never tagged the build
                    # as pending-signing
                    log.debug(f'Oh, no! We\'ve never sent {build.nvr} for signing, let\'s fix it')
                    overlooked_builds.append(build.nvr)
            session.flush()

        if stuck_builds:
            kc.multicall = True
            for b in stuck_builds:
                kc.untagBuild(pending_signing_tag, b, force=True)
            kc.multiCall()
            for b in stuck_builds:
                kc.tagBuild(pending_signing_tag, b, force=True)
            kc.multiCall()

        if overlooked_builds:
            kc.multicall = True
            for b in overlooked_builds:
                kc.tagBuild(pending_signing_tag, b, force=True)
            kc.multiCall()
