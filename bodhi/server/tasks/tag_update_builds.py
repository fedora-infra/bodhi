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
"""Handle tagging builds for an update in Koji."""

import logging
import typing

from bodhi.server import buildsys


log = logging.getLogger(__name__)


def main(tag: str, builds: typing.List[str]):
    """Handle tagging builds for an update in Koji.

    Args:
        tag: a koji tag to apply on the builds.
        builds: list of new build added to the update.
    """
    try:
        kc = buildsys.get_session()
        kc.multicall = True
        for build in builds:
            kc.tagBuild(tag, build)
            log.info(f"Tagging build {build} in {tag}")
        kc.multiCall()
    except Exception:
        log.exception("There was an error handling tagging builds in koji.")
