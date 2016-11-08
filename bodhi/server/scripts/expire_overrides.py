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

from datetime import datetime
import logging
import os
import sys

from pyramid.paster import get_appsettings, setup_logging
from sqlalchemy import engine_from_config
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import transaction

from ..buildsys import setup_buildsystem
from ..models import BuildrootOverride


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)

    config_uri = argv[1]

    setup_logging(config_uri)
    log = logging.getLogger(__name__)

    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()

    setup_buildsystem(settings)

    with transaction.manager:
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
