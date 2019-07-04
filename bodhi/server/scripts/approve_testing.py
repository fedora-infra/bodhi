# Copyright © 2013-2019 Red Hat, Inc. and others.
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
"""
Generates the bodhi-approve-testing console script.

The script is responsible for commenting on updates after they reach the mandatory amount of time
spent in the testing repository.
"""

import argparse
import sys
import logging

from pyramid.paster import get_appsettings

from bodhi.server import Session, initialize_db, buildsys
from ..models import Update, UpdateStatus
from ..config import config


logger = logging.getLogger('approve-testing')


def main(argv=None):
    """
    Comment on updates that are eligible to be pushed to stable.

    Queries for updates in the testing state that have a NULL request, looping over them looking for
    updates that are eligible to be pushed to stable but haven't had comments from Bodhi to this
    effect. For each such update it finds it will add a comment stating that the update may now be
    pushed to stable.

    This function is the entry point for the bodhi-approve-testing console script.
    """
    parser = argparse.ArgumentParser(
        description='Comment on updates that are eligible to be pushed to stable.'
    )
    parser.add_argument('config_uri', help='Path to the configuration file to use')
    parser.add_argument(
        '--verbose', dest='verbose', action='store_true', default=False,
        help='Increase the verbosity level of the output')

    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)

    settings = get_appsettings(args.config_uri)
    initialize_db(settings)
    db = Session()
    buildsys.setup_buildsystem(config)

    try:
        testing = db.query(Update).filter_by(status=UpdateStatus.testing,
                                             request=None)
        for update in testing:
            update.move_to_stable(db)
            db.commit()

    except Exception as e:
        print(str(e))
        db.rollback()
        Session.remove()
        sys.exit(1)


if __name__ == '__main__':
    main()
