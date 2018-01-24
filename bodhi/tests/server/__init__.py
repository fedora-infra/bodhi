# -*- coding: utf-8 -*-
# Copyright © 2007-2018 Red Hat, Inc.
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

import mock
import sqlalchemy

from bodhi.server.models import (
    Bug, BuildrootOverride, Comment, CVE, Group, RpmPackage, Release, ReleaseState, RpmBuild,
    Update, TestGatingStatus, UpdateRequest, UpdateSeverity, UpdateType, User, TestCase)


def create_update(session, build_nvrs, release_name=u'F17'):
    """
    Use the given session to create and return an Update with the given iterable of build_nvrs.

    Each build_nvr should be a string describing the name, version, and release for the build
    separated by dashes. For example, build_nvrs might look like this:

    (u'bodhi-2.3.3-1.fc24', u'python-fedora-atomic-composer-2016.3-1.fc24')

    You can optionally pass a release_name to select a different release than the default F17, but
    the release must already exist in the database.

    Args:
        build_nvrs (iterable): An iterable of strings of NVRs to put into the update.
        release_name (basestring): The name of the release to associate with the update.
    Returns:
        bodhi.server.models.Update: The generated update.
    """
    release = session.query(Release).filter_by(name=release_name).one()
    user = session.query(User).filter_by(name=u'guest').one()

    builds = []
    for nvr in build_nvrs:
        name, version, rel = nvr.rsplit('-', 2)
        try:
            package = session.query(RpmPackage).filter_by(name=name).one()
        except sqlalchemy.orm.exc.NoResultFound:
            package = RpmPackage(name=name)
            session.add(package)
            user.packages.append(package)
            testcase = TestCase(name=u'Wat')
            session.add(testcase)
            package.test_cases.append(testcase)

        builds.append(RpmBuild(nvr=nvr, release=release, package=package, signed=True))
        session.add(builds[-1])

        # Add a buildroot override for this build
        expiration_date = datetime.utcnow()
        expiration_date = expiration_date + timedelta(days=1)
        override = BuildrootOverride(build=builds[-1], submitter=user,
                                     notes=u'blah blah blah',
                                     expiration_date=expiration_date)
        session.add(override)

    update = Update(
        title=', '.join(build_nvrs), builds=builds, user=user, request=UpdateRequest.testing,
        notes=u'Useful details!', type=UpdateType.bugfix, date_submitted=datetime(1984, 11, 2),
        requirements=u'rpmlint', stable_karma=3, unstable_karma=-3,
        test_gating_status=TestGatingStatus.passed)
    session.add(update)
    update.release = release

    return update


def populate(db):
    """
    Create some data for tests to use.

    Args:
        db (sqlalchemy.orm.session.Session): The database session.
    """
    user = User(name=u'guest')
    db.add(user)
    anonymous = User(name=u'anonymous')
    db.add(anonymous)
    provenpackager = Group(name=u'provenpackager')
    db.add(provenpackager)
    packager = Group(name=u'packager')
    db.add(packager)
    user.groups.append(packager)
    release = Release(
        name=u'F17', long_name=u'Fedora 17',
        id_prefix=u'FEDORA', version=u'17',
        dist_tag=u'f17', stable_tag=u'f17-updates',
        testing_tag=u'f17-updates-testing',
        candidate_tag=u'f17-updates-candidate',
        pending_signing_tag=u'f17-updates-testing-signing',
        pending_testing_tag=u'f17-updates-testing-pending',
        pending_stable_tag=u'f17-updates-pending',
        override_tag=u'f17-override',
        branch=u'f17', state=ReleaseState.current)
    db.add(release)
    db.flush()
    update = create_update(db, [u'bodhi-2.0-1.fc17'])
    update.type = UpdateType.bugfix
    update.severity = UpdateSeverity.medium
    bug = Bug(bug_id=12345)
    db.add(bug)
    update.bugs.append(bug)
    cve = CVE(cve_id=u"CVE-1985-0110")
    db.add(cve)
    update.cves.append(cve)

    comment = Comment(karma=1, text=u"wow. amaze.")
    db.add(comment)
    comment.user = user
    update.comments.append(comment)

    comment = Comment(karma=0, text=u"srsly.  pretty good.", anonymous=True)
    comment.user = anonymous
    db.add(comment)
    update.comments.append(comment)

    with mock.patch(target='uuid.uuid4', return_value='wat'):
        update.assign_alias()
    db.add(update)

    db.commit()
