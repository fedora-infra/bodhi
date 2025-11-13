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
Make appropriate changes to updates that reach certain karma or time-in-stable thresholds.

This script is intended to run as a regular job (cronjob or the like). It finds all updates in
UpdateStatus.testing with no request, then does one of three things. If the update does not meet
testing requirements (i.e. it doesn't have enough karma or time in testing to even be manually
pushed, or it fails gating checks), we do nothing. Otherwise, we set the date_approved
for the update if it's not already set, then choose one of the two other options.

If the update meets testing requirements, has autopush after a certain time in testing (autotime)
enabled, and has reached that threshold, we push it. Note this is the **ONLY** way updates
for releases "not composed by Bodhi" (Rawhide, ELN, Branched for the first few weeks) are ever
pushed stable. The other way updates can be autopushed stable - Update.check_karma_thresholds(),
called by Update.comment() - opts out of handling "not composed by Bodhi" release updates.

If the update meets testing requirements but does not have autotime enabled or has
not reached that threshold, we check to see if the update already has a comment saying it is
now "approved" for push to stable. If not, we post that comment, and publish the
UpdateRequirementsMetStableV1 message.
"""

import datetime
import logging

from bodhi.messages.schemas import update as update_schemas
from bodhi.server import Session, notifications, buildsys
from bodhi.server.util import transactional_session_maker
from ..models import Update, UpdateStatus, UpdateRequest
from ..config import config


log = logging.getLogger(__name__)


def main():
    """Query for updates in the testing state that have a NULL request, and run process_update."""
    db_factory = transactional_session_maker()
    try:
        with db_factory() as db:
            testing = db.query(Update).filter_by(status=UpdateStatus.testing, request=None)
            for update in testing:
                process_update(update, db)
                db.commit()
    except Exception:
        log.exception("There was an error approving testing updates.")
    finally:
        db_factory._end_session()


def autopush_update(update: Update, db: Session):
    """
    Push an update that has autopush for time enabled and has reached the required threshold.

    For releases composed by Bodhi, we set the request and leave the compose process to do the
    status change. For releases not composed by Bodhi, we do the status change here.
    """
    if not update.has_stable_comment:
        notifications.publish(update_schemas.UpdateRequirementsMetStableV1.from_dict(
            dict(update=update)))
    log.info(f"Automatically marking {update.alias} as stable")
    # For releases composed by Bodhi, just set the request, and leave
    # the rest to the composer
    if update.release.composed_by_bodhi:
        update.set_request(db=db, action=UpdateRequest.stable, username="bodhi")
        return
    # For releases not composed by Bodhi, do all the work here
    # Both side-tag and non-side-tag updates
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
        else:
            update.status = UpdateStatus.obsolete
            update.remove_tag(update.release.pending_testing_tag)
            update.remove_tag(update.release.candidate_tag)
        db.commit()
        log.info(f"{update.alias} has conflicting builds - bailing")
        return
    update.add_tag(update.release.stable_tag)
    update.status = UpdateStatus.stable
    update.request = None
    update.pushed = True
    update.date_stable = datetime.datetime.now(datetime.timezone.utc)
    update.comment(db, "This update has been submitted for stable by bodhi",
                   author=u'bodhi')
    update.modify_bugs()
    db.commit()
    if update.from_tag:
        # Merging the side tag should happen here
        pending_signing_tag = update.release.get_pending_signing_side_tag(
            update.from_tag)
        testing_tag = update.release.get_pending_testing_side_tag(update.from_tag)
        update.remove_tag(pending_signing_tag)
        update.remove_tag(testing_tag)
        update.remove_tag(update.from_tag)
        # Delete side-tag and its children after Update has enter stable
        # We can't fully rely on Koji's auto-purge-when-empty because
        # there may be older nvrs tagged in the side-tag
        koji = buildsys.get_session()
        koji.multicall = True
        koji.deleteTag(pending_signing_tag)
        koji.deleteTag(testing_tag)
        koji.deleteTag(update.from_tag)
        koji.multiCall()
    else:
        # Non side-tag updates
        update.remove_tag(update.release.pending_testing_tag)
        update.remove_tag(update.release.pending_stable_tag)
        update.remove_tag(update.release.pending_signing_tag)
        update.remove_tag(update.release.testing_tag)
        update.remove_tag(update.release.candidate_tag)


def approved_comment_message(update: Update, db: Session):
    """Post "approved" comment and publish UpdatesRequirementsMetStable message."""
    # If this update was already commented, skip it
    if update.has_stable_comment:
        log.info(f"{update.alias} has already the comment that it can be pushed to stable - "
                 "bailing")
        return
    # post the comment
    update.comment(
        db,
        str(config.get('testing_approval_msg')),
        author='bodhi',
        # Only send email notification about the update reaching
        # testing approval on releases composed by bodhi
        email_notification=update.release.composed_by_bodhi
    )
    # publish the message
    notifications.publish(update_schemas.UpdateRequirementsMetStableV1.from_dict(
        dict(update=update)))


def process_update(update: Update, db: Session):
    """
    Check requirements, update date_approved, then call appropriate handler function.

    In all cases, this will set date_approved if the update "meets testing requirements" -
    which means it has reached either the minimum karma or time threshold to be pushed
    stable, and its gating status is passed - and that date has not been set before.

    After that, if the update has automatic push for time enabled and has reached the required
    time threshold, this will call autopush_update to handle pushing it. It is intentional
    that we do not called approved_comment_message() in this case - there is no point alerting
    the maintainer that the update can be pushed manually if we are already going to push it
    automatically. See issue #3846.

    Otherwise - if the update is approved but is not being autopushed for time - this will
    call approved_comment_message() to post the approval comment and publish the
    UpdateRequirementsMetStable message, if it has not been done before.

    It has not yet proven necessary to check the karma autopush threshold here. For releases that
    are "composed by Bodhi", Update.check_karma_thresholds() pushes updates as soon as they
    reach the karma autopush threshold. For releases that are not "composed by Bodhi", on update
    creation, autotime is forced to True and the time threshold is forced to 0, thus updates for
    these releases are *always* eligible for autotime push here, as soon as they pass gating,
    there is no case in which autokarma would be relevant.

    Args:
        update: an update in testing that may be ready for stable.
        db: a database session.
    """
    # meets_testing_requirements will be True if all non-karma / non-time
    # requirements are met, and the update has reached the minimum karma
    # threshold or wait period for a manual push to be allowed, so this
    # means "update is eligible to be manually pushed stable"
    if not update.meets_testing_requirements:
        log.info(f"{update.alias} has not met testing requirements - bailing")
        return
    log.info(f'{update.alias} now meets testing requirements')
    # always set date_approved, if it has never been set before: this
    # date indicates "first date update became eligible for manual push"
    if not update.date_approved:
        update.date_approved = datetime.datetime.now(datetime.timezone.utc)
    if update.autotime and update.days_in_testing >= update.stable_days:
        # if update *additionally* meets the time-based autopush threshold,
        # push it
        autopush_update(update, db)
    else:
        # otherwise, post the comment and publish the message announcing
        # it is eligible for manual push, if this has not been done
        approved_comment_message(update, db)

    log.info(f'{update.alias} processed by approve_testing')
