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
"""Comment on updates after they reach the mandatory amount of time in the testing repository."""

import logging

from sqlalchemy import func

from bodhi.messages.schemas import update as update_schemas
from bodhi.server import Session, notifications, buildsys
from bodhi.server.util import transactional_session_maker
from ..models import Update, UpdateStatus, UpdateRequest
from ..config import config


log = logging.getLogger(__name__)


def main():
    """
    Comment on updates that are eligible to be pushed to stable.

    Queries for updates in the testing state that have a NULL request, and run approve_update on
    them.
    """
    db_factory = transactional_session_maker()
    try:
        with db_factory() as db:
            testing = db.query(Update).filter_by(status=UpdateStatus.testing, request=None)
            for update in testing:
                approve_update(update, db)
                db.commit()
    except Exception:
        log.exception("There was an error approving testing updates.")
    finally:
        db_factory._end_session()


def approve_update(update: Update, db: Session):
    """Add a comment to an update if it is ready for stable.

    Check that the update is eligible to be pushed to stable but hasn't had comments from Bodhi to
    this effect. Add a comment stating that the update may now be pushed to stable.

    Args:
        update: an update in testing that may be ready for stable.
    """
    if not update.release.mandatory_days_in_testing and not update.autotime:
        # If this release does not have any testing requirements and is not autotime,
        # skip it
        log.info(f"{update.release.name} doesn't have mandatory days in testing")
        return
    # If this update was already commented, skip it
    if update.has_stable_comment:
        return
    # If updates have reached the testing threshold, say something! Keep in mind
    # that we don't care about karma here, because autokarma updates get their request set
    # to stable by the Update.comment() workflow when they hit the required threshold. Thus,
    # this function only needs to consider the time requirements because these updates have
    # not reached the karma threshold.
    if not update.meets_testing_requirements:
        return
    log.info(f'{update.alias} now meets testing requirements')
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
        log.info(f"Automatically marking {update.alias} as stable")
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
                update.request = None
                if update.from_tag is not None:
                    update.status = UpdateStatus.pending
                    update.remove_tag(
                        update.release.get_testing_side_tag(update.from_tag))
                else:
                    update.status = UpdateStatus.obsolete
                    update.remove_tag(update.release.pending_testing_tag)
                    update.remove_tag(update.release.candidate_tag)
                db.commit()
                return
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
