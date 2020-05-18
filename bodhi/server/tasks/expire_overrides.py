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
"""Look for overrides that are past their expiration dates and mark them expired."""

from datetime import datetime
import logging

from bodhi.server import Session
from bodhi.server.util import transactional_session_maker
from ..models import BuildrootOverride


log = logging.getLogger(__name__)


def main():
    """Wrap ``expire_overrides()``, catching exceptions."""
    db_factory = transactional_session_maker()
    try:
        with db_factory() as db:
            expire_overrides(db)
    except Exception:
        log.exception("There was an error expiring overrides")


def expire_overrides(db: Session):
    """Search for overrides that are past their expiration date and mark them expired."""
    now = datetime.utcnow()
    overrides = db.query(BuildrootOverride)
    overrides = overrides.filter(BuildrootOverride.expired_date.is_(None))
    overrides = overrides.filter(BuildrootOverride.expiration_date < now)
    count = overrides.count()
    if not count:
        log.info("No active buildroot override to expire")
        return
    log.info("Expiring %d buildroot overrides...", count)
    for override in overrides:
        log.debug(f"Expiring BRO for {override.build.nvr} because it's due to expire.")
        override.expire()
        db.add(override)
        log.info("Expired %s" % override.build.nvr)
