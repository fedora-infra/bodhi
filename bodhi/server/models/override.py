# Copyright © 2011-2019 Red Hat, Inc. and others.
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
"""Bodhi's override models."""

from datetime import datetime

from sqlalchemy import and_, Column, DateTime, ForeignKey, Integer, Unicode
from sqlalchemy.orm import relationship, backref
import pyramid

from bodhi.messages.schemas import buildroot_override as override_schemas
from bodhi.server import buildsys, log, notifications
from bodhi.server.models import Base, Build


class BuildrootOverride(Base):
    """
    This model represents a Koji buildroot override.

    A buildroot override is a way to add a build to the Koji buildroot (the set of packages used
    to build a package) manually. Normally, builds are only available after they are pushed to
    "stable", but this allows a build to be added to the buildroot immediately. This is useful
    for updates that depend on each other to be built.

    Attributes:
        notes (str): A text field that holds arbitrary notes about the buildroot override.
        submission_date (DateTime): The date that the buildroot override was submitted.
        expiration_date (DateTime): The date that the buildroot override expires.
        expired_date (DateTime): The date that the buildroot override expired.
        build_id (int): The primary key of the :class:`Build` this override is related to.
        build (Build): The build this override is related to.
        submitter_id (int): The primary key of the :class:`User` this override was created by.
        submitter (User): The user this override was created by.
    """

    __tablename__ = 'buildroot_overrides'
    __include_extras__ = ('nvr',)
    __get_by__ = ('build_id',)

    build_id = Column(Integer, ForeignKey('builds.id'), nullable=False)
    submitter_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    notes = Column(Unicode, nullable=False)

    submission_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    expiration_date = Column(DateTime, nullable=False)
    expired_date = Column(DateTime)

    build = relationship('Build', lazy='joined',
                         backref=backref('override', lazy='joined',
                                         uselist=False))
    submitter = relationship('User', lazy='joined',
                             backref=backref('buildroot_overrides',
                                             lazy='joined'))

    @property
    def nvr(self) -> str:
        """
        Return the NVR of the :class:`Build` associated with this override.

        Returns:
            The override's :class:`Build's <Build>` NVR.
        """
        return self.build.nvr

    @classmethod
    def new(cls, request: 'pyramid.request', **data) -> 'BuildrootOverride':
        """
        Create a new buildroot override.

        Args:
            request: The current web request.
            data: A dictionary of all the attributes to be used on the new override.
        Returns:
            The newly created BuildrootOverride instance.
        """
        db = request.db

        build = data['build']

        if build.override is not None:
            request.errors.add('body', 'nvr',
                               '%s is already in a override' % build.nvr)
            return

        old_build = db.query(Build).filter(
            and_(
                Build.package_id == build.package_id,
                Build.release_id == build.release_id)).first()

        if old_build is not None and old_build.override is not None:
            # There already is a buildroot override for an older build of this
            # package in this release. Expire it
            log.debug(f"Expiring BRO for {old_build.nvr} because it's superseded by {build.nvr}.")
            old_build.override.expire()
            db.add(old_build.override)

        override = cls(**data)
        override.enable()
        db.add(override)
        db.flush()

        return override

    @classmethod
    def edit(cls, request: 'pyramid.request', **data) -> 'BuildrootOverride':
        """
        Edit an existing buildroot override.

        Args:
            request: The current web request.
            data: The changed being made to the BuildrootOverride.
        Returns:
            The new updated override.
        """
        db = request.db

        edited = data.pop('edited')
        override = cls.get(edited.id)

        if override is None:
            request.errors.add('body', 'edited',
                               'No buildroot override for this build')
            return

        override.submitter = data['submitter']
        override.notes = data['notes']
        override.expiration_date = data['expiration_date']
        if 'submission_date' in data:
            override.submission_date = data['submission_date']

        now = datetime.utcnow()

        if override.expired_date is not None and override.expiration_date > now:
            # Buildroot override had expired, we need to unexpire it
            override.enable()

        elif data['expired']:
            log.debug(f"Expiring BRO for {override.build.nvr} because it was edited.")
            override.expire()

        db.add(override)
        db.flush()

        return override

    def enable(self) -> None:
        """Mark the BuildrootOverride as enabled."""
        koji_session = buildsys.get_session()
        koji_session.tagBuild(self.build.release.override_tag, self.build.nvr)

        notifications.publish(override_schemas.BuildrootOverrideTagV1.from_dict(
            dict(override=self)))

        self.expired_date = None

    def expire(self) -> None:
        """Mark the BuildrootOverride as expired."""
        if self.expired_date is not None:
            return

        koji_session = buildsys.get_session()
        try:
            koji_session.untagBuild(self.build.release.override_tag,
                                    self.build.nvr, strict=True)
        except Exception as e:
            log.error('Unable to untag override %s: %s' % (self.build.nvr, e))
        self.expired_date = datetime.utcnow()

        notifications.publish(override_schemas.BuildrootOverrideUntagV1.from_dict(
            {'override': self}))
