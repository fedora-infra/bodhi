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
"""Query the wiki for test cases for each package on the given update."""

import logging

from bodhi.server.exceptions import BodhiException, ExternalCallException
from bodhi.server.util import transactional_session_maker


log = logging.getLogger(__name__)


def main(alias: str):
    """
    Query the wiki for test cases for each package on the given update.

    Args:
        alias: The update's builds are iterated upon to find test cases for
            them.
    """
    from bodhi.server.models import Update

    db_factory = transactional_session_maker()
    with db_factory() as session:
        update = Update.get(alias)
        if not update:
            raise BodhiException(f"Couldn't find alias {alias} in DB")

        for build in update.builds:
            try:
                build.update_test_cases(session)
            except ExternalCallException:
                log.warning('Error occurred during fetching testcases', exc_info=True)
                raise ExternalCallException
