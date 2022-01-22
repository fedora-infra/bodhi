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
"""Utility functions for message consumers."""

import logging

from bodhi.server.models import Build, Update

log = logging.getLogger(__name__)


def update_from_db_message(msgid: str, itemdict: dict):
    """
    Find and return update for waiverdb or resultsdb message.

    Used by the resultsdb and waiverdb consumers.

    Args:
        msgid:    the message ID (for logging purposes)
        itemdict: the relevant dict from the message. 'subject' dict
                  for a waiverdb message, 'item' dict for resultsdb.
    Returns:
        bodhi.server.models.Update or None: the relevant update, if
                                            found.
    """
    itemtype = itemdict.get("type")
    if not itemtype:
        log.error(f"Couldn't find item type in message {msgid}")
        return None
    if isinstance(itemtype, list):
        # In resultsdb.result.new messages, the values are all lists
        # for some reason
        itemtype = itemtype[0]
    if itemtype not in ("koji_build", "bodhi_update"):
        log.debug(f"Irrelevant item type {itemtype}")
        return None

    # find the update
    if itemtype == "bodhi_update":
        updateid = itemdict.get("item")
        if isinstance(updateid, list):
            updateid = updateid[0]
        if not updateid:
            log.error(f"Couldn't find update ID in message {msgid}")
            return None
        update = Update.get(updateid)
        if not update:
            log.error(f"Couldn't find update {updateid} in DB")
            return None
    else:
        nvr = itemdict.get("nvr", itemdict.get("item"))
        if isinstance(nvr, list):
            nvr = nvr[0]
        if not nvr:
            log.error(f"Couldn't find nvr in message {msgid}")
            return None
        build = Build.get(nvr)
        if not build:
            log.error(f"Couldn't find build {nvr} in DB")
            return None
        update = build.update

    return update
