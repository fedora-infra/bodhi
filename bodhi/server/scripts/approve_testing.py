# -*- coding: utf-8 -*-
# Copyright © 2013-2017 Red Hat, Inc. and others.
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

import os
import sys

from pyramid.paster import get_appsettings
import six

from ..models import Update, UpdateStatus
from ..config import config
from bodhi.server import Session, initialize_db, notifications


def usage(argv):
    """
    Print usage information and exit with code 1.

    Args:
        argv (list): The arguments that were passed to the CLI from sys.argv.
    """
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    """
    Comment on updates that are eligible to be pushed to stable.

    Queries for updates in the testing state that have a NULL request, looping over them looking for
    updates that are eligible to be pushed to stable but haven't had comments from Bodhi to this
    effect. For each such update it finds it will add a comment stating that the update may now be
    pushed to stable.

    This function is the entry point for the bodhi-approve-testing console script.

    Args:
        argv (list): A list of command line arguments. Defaults to sys.argv.
    """
    if len(argv) != 2:
        usage(argv)

    settings = get_appsettings(argv[1])
    initialize_db(settings)
    db = Session()

    try:
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

            # Approval message when testing based on karma threshold
            if update.stable_karma not in (0, None) and update.karma >= update.stable_karma \
                    and not update.autokarma and update.meets_testing_requirements:
                print('%s now reaches stable karma threshold' % update.title)
                text = config.get('testing_approval_msg_based_on_karma')
                update.comment(db, text, author=u'bodhi')
                continue

            # If autokarma updates have reached the testing threshold, say something! Keep in mind
            # that we don't care about karma here, because autokarma updates get their request set
            # to stable by the Update.comment() workflow when they hit the required threshold. Thus,
            # this function only needs to consider the time requirements because these updates have
            # not reached the karma threshold.
            if update.meets_testing_requirements:
                print('%s now meets testing requirements' % update.title)
                text = six.text_type(
                    config.get('testing_approval_msg') % update.mandatory_days_in_testing)
                update.comment(db, text, author=u'bodhi')

                notifications.publish(
                    topic='update.requirements_met.stable',
                    msg=dict(update=update))

        db.commit()
    except Exception as e:
        print(str(e))
        db.rollback()
        Session.remove()
        sys.exit(1)
