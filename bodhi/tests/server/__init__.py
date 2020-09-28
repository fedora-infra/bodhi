# Copyright © 2007-2019 Red Hat, Inc.
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
"""Test the bodhi.server package."""

from datetime import datetime, timedelta
from unittest import mock

import sqlalchemy

from bodhi.server.models import (
    Bug, BuildrootOverride, Comment, Group, RpmPackage, Release, ReleaseState, RpmBuild,
    Update, UpdateRequest, UpdateSeverity, UpdateType, User, TestCase, PackageManager)


def create_update(session, build_nvrs, release_name='F17'):
    """
    Use the given session to create and return an Update with the given iterable of build_nvrs.

    Each build_nvr should be a string describing the name, version, and release for the build
    separated by dashes. For example, build_nvrs might look like this:

    ('bodhi-2.3.3-1.fc24', 'python-fedora-atomic-composer-2016.3-1.fc24')

    You can optionally pass a release_name to select a different release than the default F17, but
    the release must already exist in the database.

    Args:
        build_nvrs (iterable): An iterable of strings of NVRs to put into the update.
        release_name (str): The name of the release to associate with the update.
    Returns:
        bodhi.server.models.Update: The generated update.
    """
    release = session.query(Release).filter_by(name=release_name).one()
    user = session.query(User).filter_by(name='guest').one()

    builds = []
    for nvr in build_nvrs:
        name, version, rel = nvr.rsplit('-', 2)
        try:
            package = session.query(RpmPackage).filter_by(name=name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            package = RpmPackage(name=name)
            session.add(package)

        try:
            testcase = session.query(TestCase).filter_by(name='Wat').one()
        except sqlalchemy.orm.exc.NoResultFound:
            testcase = TestCase(name='Wat')
            session.add(testcase)

        build = RpmBuild(nvr=nvr, release=release, package=package, signed=True)
        build.testcases.append(testcase)
        builds.append(build)
        session.add(build)

        # Add a buildroot override for this build
        expiration_date = datetime.utcnow()
        expiration_date = expiration_date + timedelta(days=1)
        override = BuildrootOverride(build=build, submitter=user,
                                     notes='blah blah blah',
                                     expiration_date=expiration_date)
        session.add(override)

    update = Update(
        builds=builds, user=user, request=UpdateRequest.testing,
        notes='Useful details!', type=UpdateType.bugfix, date_submitted=datetime(1984, 11, 2),
        requirements='rpmlint', stable_karma=3, unstable_karma=-3, release=release)
    session.add(update)
    return update


def populate(db):
    """
    Create some data for tests to use.

    Args:
        db (sqlalchemy.orm.session.Session): The database session.
    """
    user = User(name='guest')
    db.add(user)
    anonymous = User(name='anonymous')
    db.add(anonymous)
    provenpackager = Group(name='provenpackager')
    db.add(provenpackager)
    packager = Group(name='packager')
    db.add(packager)
    user.groups.append(packager)
    release = Release(
        name='F17', long_name='Fedora 17',
        id_prefix='FEDORA', version='17',
        dist_tag='f17', stable_tag='f17-updates',
        testing_tag='f17-updates-testing',
        candidate_tag='f17-updates-candidate',
        pending_signing_tag='f17-updates-signing-pending',
        pending_testing_tag='f17-updates-testing-pending',
        pending_stable_tag='f17-updates-pending',
        override_tag='f17-override',
        branch='f17', state=ReleaseState.current,
        create_automatic_updates=True,
        package_manager=PackageManager.unspecified, testing_repository=None)
    db.add(release)
    db.flush()
    # This mock will help us generate a consistent update alias.
    with mock.patch(target='uuid.uuid4', return_value='wat'):
        update = create_update(db, ['bodhi-2.0-1.fc17'])
    update.type = UpdateType.bugfix
    update.severity = UpdateSeverity.medium
    bug = Bug(bug_id=12345)
    db.add(bug)
    update.bugs.append(bug)

    comment = Comment(karma=1, text="wow. amaze.")
    db.add(comment)
    comment.user = user
    update.comments.append(comment)

    comment = Comment(karma=0, text="srsly.  pretty good.")
    comment.user = anonymous
    db.add(comment)
    update.comments.append(comment)

    db.add(update)

    db.commit()
