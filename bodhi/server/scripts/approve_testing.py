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

from ..models import Update, UpdateStatus
from ..config import config


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) != 2:
        usage(argv)

    db = _get_db_session(argv[1])

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

            # Approval message when testing based on karma threshold
            if update.stable_karma not in (0, None) and update.karma >= update.stable_karma \
                    and not update.autokarma and update.meets_testing_requirements:
                print('%s now reaches stable karma threshold' % update.title)
                text = unicode(config.get('testing_approval_msg_based_on_karma'))
                update.comment(db, text, author=u'bodhi')
                continue

            # If autokarma updates have reached the testing threshold, say something! Keep in mind
            # that we don't care about karma here, because autokarma updates get their request set
            # to stable by the Update.comment() workflow when they hit the required threshold. Thus,
            # this function only needs to consider the time requirements because these updates have
            # not reached the karma threshold.
            if update.meets_testing_requirements:
                print('%s now meets testing requirements' % update.title)
                text = unicode(
                    config.get('testing_approval_msg') % update.release.mandatory_days_in_testing)
                update.comment(db, text, author=u'bodhi')


def _get_db_session(config_uri):
    """
    Construct and return a database session using settings from the given config_uri.

    :param config_uri: A path to a config file to use to get the db settings.
    :type  config_uri: basestring
    :return:           A database session
    """
    # There are many blocks of code like this in the codebase. We should consolidate them into a
    # single utility function as described in https://github.com/fedora-infra/bodhi/issues/1028
    settings = get_appsettings(config_uri)
    engine = engine_from_config(settings, 'sqlalchemy.')
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    return Session()
