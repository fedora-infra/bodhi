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

import os
import sys
import logging

from pyramid.paster import get_appsettings
from sqlalchemy import func

from bodhi.messages.schemas import update as update_schemas
from bodhi.server import Session, initialize_db, notifications, buildsys
from ..models import Update, UpdateStatus, UpdateRequest
from ..config import config


logger = logging.getLogger('approve-testing')


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
    logging.basicConfig(level=logging.ERROR)

    if len(argv) != 2:
        usage(argv)

    settings = get_appsettings(argv[1])
    initialize_db(settings)
    db = Session()
    buildsys.setup_buildsystem(config)

    try:
        testing = db.query(Update).filter_by(status=UpdateStatus.testing,
                                             request=None)
        for update in testing:
            if not update.release.mandatory_days_in_testing and not update.autotime:
                # If this release does not have any testing requirements and is not autotime,
                # skip it
                print(f"{update.release.name} doesn't have mandatory days in testing")
                continue

            # If this update was already commented, skip it
            if update.has_stable_comment:
                continue

            # If updates have reached the testing threshold, say something! Keep in mind
            # that we don't care about karma here, because autokarma updates get their request set
            # to stable by the Update.comment() workflow when they hit the required threshold. Thus,
            # this function only needs to consider the time requirements because these updates have
            # not reached the karma threshold.
            if update.meets_testing_requirements:
                print(f'{update.alias} now meets testing requirements')
                # Only send email notification about the update reaching
                # testing approval on releases composed by bodhi
                update.comment(
                    db,
                    str(config.get('testing_approval_msg')),
                    author='bodhi',
                    email_notification=update.release.composed_by_bodhi
                )

                notifications.publish(update_schemas.UpdateRequirementsMetStableV1.from_dict(
                    dict(update=update)))

                if update.autotime and update.days_in_testing >= update.stable_days:
                    print(f"Automatically marking {update.alias} as stable")
                    # For now only rawhide update can be created using side tag
                    # Do not add the release.pending_stable_tag if the update
                    # was created from a side tag.
                    if update.release.composed_by_bodhi:
                        update.set_request(db=db, action=UpdateRequest.stable, username="bodhi")
                    # For updates that are not included in composes run by bodhi itself,
                    # mark them as stable
                    else:
                        # Single and Multi build update
                        conflicting_builds = update.find_conflicting_builds()
                        if conflicting_builds:
                            builds_str = str.join(", ", conflicting_builds)
                            update.comment(
                                db,
                                "This update cannot be pushed to stable. "
                                f"These builds {builds_str} have a more recent "
                                f"build in koji's {update.release.stable_tag} tag.",
                                author="bodhi")
                            update.status = UpdateStatus.pending
                            update.request = None
                            update.remove_tag(update.release.get_testing_side_tag(update.from_tag))
                            db.commit()
                            continue

                        update.add_tag(update.release.stable_tag)
                        update.status = UpdateStatus.stable
                        update.request = None
                        update.pushed = True
                        update.date_stable = update.date_pushed = func.current_timestamp()
                        update.comment(db, "This update has been submitted for stable by bodhi",
                                       author=u'bodhi')

                        # Multi build update
                        if update.from_tag:
                            # Merging the side tag should happen here
                            pending_signing_tag = update.release.get_pending_signing_side_tag(
                                update.from_tag)
                            testing_tag = update.release.get_testing_side_tag(update.from_tag)

                            update.remove_tag(pending_signing_tag)
                            update.remove_tag(testing_tag)
                            update.remove_tag(update.from_tag)

                            koji = buildsys.get_session()
                            koji.deleteTag(pending_signing_tag)
                            koji.deleteTag(testing_tag)

                            # Removes the tag and the build target from koji.
                            koji.removeSideTag(update.from_tag)
                        else:
                            # Single build update
                            update.remove_tag(update.release.pending_testing_tag)
                            update.remove_tag(update.release.pending_stable_tag)
                            update.remove_tag(update.release.pending_signing_tag)
                            update.remove_tag(update.release.candidate_tag)

                db.commit()

    except Exception as e:
        print(str(e))
        db.rollback()
        Session.remove()
        sys.exit(1)
