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

"""Check the enforced policies by Greenwave for each open update."""
import logging

from bodhi.server import models
from bodhi.server.util import transactional_session_maker


log = logging.getLogger(__name__)


def main():
    """Check the enforced policies by Greenwave for each open update."""
    db_factory = transactional_session_maker()
    with db_factory() as session:

        updates = models.Update.query.filter(
            models.Update.status.in_(
                [models.UpdateStatus.pending, models.UpdateStatus.testing])
        ).filter(
            models.Update.release_id == models.Release.id
        ).filter(
            models.Release.state.in_([
                models.ReleaseState.current,
                models.ReleaseState.pending,
                models.ReleaseState.frozen,
            ])
        ).order_by(
            # Check the older updates first so there is more time for the newer to
            # get their test results
            models.Update.id.asc()
        )

        for update in updates:
            try:
                update.update_test_gating_status()
                session.commit()
            except Exception:
                # If there is a problem talking to Greenwave server, print the error.
                log.exception(f"There was an error checking the policy for {update.alias}")
                session.rollback()
