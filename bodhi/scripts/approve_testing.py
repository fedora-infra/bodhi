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
This script is responsible for commenting on updates after they reach the
mandatory amount of time spent in the testing repository.
"""

import os
import sys

from pyramid.paster import get_appsettings
from sqlalchemy import engine_from_config
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction

from ..models import Base, Update, UpdateStatus
from ..config import config


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)

    config_uri = argv[1]

    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()

    with transaction.manager:
        testing = db.query(Update).filter_by(status=UpdateStatus.testing,
                                             request=None)
        for update in testing:
            # If this release does not have any testing requirements, skip it
            if not update.release.mandatory_days_in_testing:
                print('%s doesn\'t have mandatory days in testing' % update.release.name)
                continue
            # If this has already met testing requirements, skip it
            if update.met_testing_requirements:
                continue
            if update.meets_testing_requirements:
                print('%s now meets testing requirements' % update.title)
                text = config.get('testing_approval_msg') % update.days_in_testing
                update.comment(db, text, author='bodhi')

            # Approval message when testing based on karma threshold
            if update.stable_karma not in (0, None) and update.karma >= update.stable_karma \
                    and not update.autokarma:
                print('%s now reaches stable karma threshold' % update.title)
                text = config.get('testing_approval_msg_based_on_karma')
                update.comment(db, text, author='bodhi')
