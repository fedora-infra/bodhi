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
"""Handle side-tags and related tags for updates in Koji."""

import logging
import typing

from bodhi.server import buildsys
from bodhi.server.models import Update


log = logging.getLogger(__name__)


def main(updates: typing.List[Update], from_tag: str):
    """Handle side-tags and related tags for updates in Koji.

    Args:
        updates: one or more Update objects
        from_tag: the tag into which the builds were built
    """
    koji = buildsys.get_session()
    for update in updates:
        release = update.release
        if not release.composed_by_bodhi:
            # Before the Bodhi activation point of a release, keep builds tagged
            # with the side-tag and its associate tags. Validate that
            # <koji_tag>-pending-signing and <koji-tag>-testing exists, if not create
            # them.
            side_tag_signing_pending = update.release.get_pending_signing_side_tag(
                from_tag
            )
            side_tag_testing_pending = update.release.get_testing_side_tag(from_tag)
            if not koji.getTag(side_tag_signing_pending):
                koji.createTag(side_tag_signing_pending, parent=from_tag)
            if not koji.getTag(side_tag_testing_pending):
                koji.createTag(side_tag_testing_pending, parent=from_tag)
                koji.editTag2(side_tag_testing_pending, perm="autosign")

            to_tag = side_tag_signing_pending
            # Move every new build to <from_tag>-signing-pending tag
            update.add_tag(to_tag)
        else:
            # After the Bodhi activation point of a release, add the pending-signing tag
            # of the release to funnel the builds back into a normal workflow for a
            # stable release.
            update.add_tag(release.pending_signing_tag)

            # From here on out, we don't need the side-tag anymore.
            koji.removeSideTag(from_tag)
