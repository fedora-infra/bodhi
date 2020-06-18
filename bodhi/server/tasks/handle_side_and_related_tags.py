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


log = logging.getLogger(__name__)


def main(builds: typing.List[str],
         pending_signing_tag: str,
         from_tag: str,
         pending_testing_tag: typing.Optional[str],
         candidate_tag: typing.Optional[str]):
    """Handle side-tags and related tags for updates in Koji.

    Args:
        builds: a list of builds to be tagged.
        pending_signing_tag: the pending signing tag to apply on the builds.
        from_tag: the tag into which the builds were built.
        pending_testing_tag: the pending_testing_tag to create if not None.
        candidate_tag: the candidate tag needed for update that are composed by bodhi.
    """
    try:
        koji = buildsys.get_session()

        tags = [pending_signing_tag]
        if pending_testing_tag is not None:
            # Validate that <koji_tag>-pending-signing and <koji-tag>-testing-signing exists
            # if not create them.
            if not koji.getTag(pending_signing_tag):
                log.info(f"Create {pending_signing_tag} in koji")
                koji.createTag(pending_signing_tag, parent=from_tag)
            if not koji.getTag(pending_testing_tag):
                log.info(f"Create {pending_testing_tag} in koji")
                koji.createTag(pending_testing_tag, parent=from_tag)
                koji.editTag2(pending_testing_tag, perm="autosign")
        elif candidate_tag is not None:
            # If we don't provide a pending_testing_tag, then we have merged the
            # side tag into the release pending_signing and candidate tag.
            # We can remove the side tag.
            tags.append(candidate_tag)

        koji.multicall = True
        for b in builds:
            for t in tags:
                log.info(f"Tagging build {b} in {t}")
                koji.tagBuild(t, b)
        koji.multiCall()

    except Exception:
        log.exception("There was an error handling side-tags updates")
