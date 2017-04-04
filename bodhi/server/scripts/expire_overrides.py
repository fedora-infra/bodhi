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
"""Contains the code that is used to generate the bodhi-expire-overrides server CLI."""

from datetime import datetime
import logging
import os
import sys

from pyramid.paster import get_appsettings, setup_logging

from ..buildsys import setup_buildsystem
from ..models import BuildrootOverride
from bodhi.server import Session, initialize_db


def usage(argv):
    """
    Print usage info and exit(1).

    Args:
        argv (list): The command line arguments that were passed to the CLI from sys.argv.
    """
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    """
    Search for overrides that are past their expiration date and mark them expired.

    Args:
        argv (list): The command line arguments. Defaults to sys.argv.
    """
    if len(argv) != 2:
        usage(argv)

    config_uri = argv[1]

    setup_logging(config_uri)
    log = logging.getLogger(__name__)

    settings = get_appsettings(config_uri)
    initialize_db(settings)
    db = Session()

    setup_buildsystem(settings)

    try:
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
            override.expire()
            db.add(override)
            log.info("Expired %s" % override.build.nvr)
        db.commit()
    except Exception as e:
        log.error(e)
        db.rollback()
        Session.remove()
        sys.exit(1)
