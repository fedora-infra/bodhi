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
"""Bodhi's release models."""

from collections import defaultdict
import re
import typing

from sqlalchemy import Boolean, Column, Unicode, UnicodeText

from bodhi.server import log
from bodhi.server.config import config
from bodhi.server.models import Base, PackageManager, ReleaseState

if typing.TYPE_CHECKING:  # pragma: no cover
    import pyramid  # noqa: 401


class Release(Base):
    """
    Represent a distribution release, such as Fedora 27.

    Attributes:
        name (str): The name of the release, such as 'F27'.
        long_name (str): A human readable name for the release, such as 'Fedora 27'.
        version (str): The version of the release, such as '27'.
        id_prefix (str): The prefix to use when forming update aliases for this release, such as
            'FEDORA'.
        branch (str): The dist-git branch associated with this release, such as 'f27'.
        dist_tag (str): The koji dist_tag associated with this release, such as 'f27'.
        stable_tag (str): The koji tag to be used for stable builds in this release, such as
            'f27-updates'.
        testing_tag (str): The koji tag to be used for testing builds in this release, such as
            'f27-updates-testing'.
        candidate_tag (str): The koji tag used for builds that are candidates to be updates,
            such as 'f27-updates-candidate'.
        pending_signing_tag (str): The koji tag that specifies that a build is waiting to be
            signed, such as 'f27-signing-pending'.
        pending_testing_tag (str): The koji tag that indicates that a build is waiting to be
            composed into the testing repository, such as 'f27-updates-testing-pending'.
        pending_stable_tag (str): The koji tag that indicates that a build is waiting to be
            composed into the stable repository, such as 'f27-updates-pending'.
        override_tag (str): The koji tag that is used when a build is added as a buildroot
            override, such as 'f27-override'.
        mail_template (str): The notification mail template.
        state (:class:`ReleaseState`): The current state of the release. Defaults to
            ``ReleaseState.disabled``.
        id (int): The primary key of this release.
        builds (sqlalchemy.orm.collections.InstrumentedList): An iterable of :class:`Builds <Build>`
            associated with this release.
        composed_by_bodhi (bool): The flag that indicates whether the release is composed by
            Bodhi or not. Defaults to True.
        create_automatic_updates (bool): A flag indicating that updates should
            be created automatically for Koji builds tagged into the
            `candidate_tag`. Defaults to False.
        package_manager (EnumSymbol): The package manager this release uses. This must be one of
            the values defined in :class:`PackageManager`.
        testing_repository (str): The name of repository where updates are placed for
            testing before being pushed to the main repository.
    """

    __tablename__ = 'releases'
    __exclude_columns__ = ('id', 'builds')
    __get_by__ = ('name', 'long_name', 'dist_tag')

    name = Column(Unicode(10), unique=True, nullable=False)
    long_name = Column(Unicode(25), unique=True, nullable=False)
    version = Column(Unicode(5), nullable=False)
    id_prefix = Column(Unicode(25), nullable=False)
    branch = Column(Unicode(10), nullable=False)

    dist_tag = Column(Unicode(20), nullable=False)
    stable_tag = Column(UnicodeText, nullable=False)
    testing_tag = Column(UnicodeText, nullable=False)
    candidate_tag = Column(UnicodeText, nullable=False)
    pending_signing_tag = Column(UnicodeText, nullable=False)
    pending_testing_tag = Column(UnicodeText, nullable=False)
    pending_stable_tag = Column(UnicodeText, nullable=False)
    override_tag = Column(UnicodeText, nullable=False)
    mail_template = Column(UnicodeText, default='fedora_errata_template', nullable=False)

    state = Column(ReleaseState.db_type(), default=ReleaseState.disabled, nullable=False)
    composed_by_bodhi = Column(Boolean, default=True)
    create_automatic_updates = Column(Boolean, default=False)

    _version_int_regex = re.compile(r'\D+(\d+)[CMF]?$')

    package_manager = Column(PackageManager.db_type(), default=PackageManager.unspecified)
    testing_repository = Column(UnicodeText, nullable=True)

    @property
    def critpath_min_karma(self) -> int:
        """
        Return the min_karma for critpath updates for this release.

        If the release doesn't specify a min_karma, the default critpath.min_karma setting is used
        instead.

        Returns:
            The minimum karma required for critical path updates for this release.
        """
        if self.setting_status:
            min_karma = config.get(
                f'{self.setting_prefix}.{self.setting_status}.critpath.min_karma', None)
            if min_karma:
                return int(min_karma)
        return config.get('critpath.min_karma')

    @property
    def version_int(self):
        """
        Return an integer representation of the version of this release.

        Returns:
            int: The version of the release.
        """
        return int(self._version_int_regex.match(self.name).groups()[0])

    @property
    def mandatory_days_in_testing(self):
        """
        Return the number of days that updates in this release must spend in testing.

        Returns:
            int: The number of days in testing that updates in this release must spend in
            testing. If the release isn't configured to have mandatory testing time, 0 is
            returned.
        """
        name = self.name.lower().replace('-', '')
        status = config.get('%s.status' % name, None)
        if status:
            days = config.get(
                '%s.%s.mandatory_days_in_testing' % (name, status))
            if days is not None:
                return int(days)
        days = config.get('%s.mandatory_days_in_testing' %
                          self.id_prefix.lower().replace('-', '_'))
        if days is None:
            log.warning('No mandatory days in testing defined for %s. Defaulting to 0.' % self.name)
            return 0
        else:
            return int(days)

    @property
    def collection_name(self):
        """
        Return the collection name of this release (eg: Fedora EPEL).

        Returns:
            str: The collection name of this release.
        """
        return ' '.join(self.long_name.split()[:-1])

    @classmethod
    def all_releases(cls):
        """
        Return a mapping of release states to a list of dictionaries describing the releases.

        Returns:
            defaultdict: Mapping strings of :class:`ReleaseState` names to lists of dictionaries
            that describe the releases in those states.
        """
        if cls._all_releases:
            return cls._all_releases
        releases = defaultdict(list)
        for release in cls.query.order_by(cls.name.desc()).all():
            releases[release.state.value].append(release.__json__())
        cls._all_releases = releases
        return cls._all_releases
    _all_releases = None

    @classmethod
    def clear_all_releases_cache(cls):
        """Clear up Release cache."""
        cls._all_releases = None

    @classmethod
    def get_tags(cls, session):
        """
        Return a 2-tuple mapping tags to releases.

        Args:
            session (sqlalchemy.orm.session.Session): A database session.
        Returns:
            tuple: A 2-tuple. The first element maps the keys 'candidate', 'testing', 'stable',
            'override', 'pending_testing', and 'pending_stable' each to a list of tags for various
            releases that correspond to those tag semantics. The second element maps each koji tag
            to the release's name that uses it.
        """
        if cls._tag_cache:
            return cls._tag_cache
        data = {'candidate': [], 'testing': [], 'stable': [], 'override': [],
                'pending_testing': [], 'pending_stable': []}
        tags = {}  # tag -> release lookup
        for release in session.query(cls).all():
            for key in data:
                tag = getattr(release, '%s_tag' % key)
                data[key].append(tag)
                tags[tag] = release.name
        cls._tag_cache = (data, tags)
        return cls._tag_cache
    _tag_cache = None

    @classmethod
    def from_tags(cls, tags, session):
        """
        Find a release associated with one of the given koji tags.

        Args:
            tags (list): A list of koji tags for which an associated release is desired.
            session (sqlalchemy.orm.session.Session): A database session.
        Returns:
            Release or None: The first release found that matches the first tag. If no release is
                found, ``None`` is returned.
        """
        tag_types, tag_rels = cls.get_tags(session)
        for tag in tags:
            if tag not in tag_rels:
                continue
            release = session.query(cls).filter_by(name=tag_rels[tag]).first()
            if release:
                return release

    @property
    def setting_prefix(self) -> str:
        """
        Return the prefix for settings that pertain to this Release.

        Returns:
            The Release's setting prefix.
        """
        return self.name.lower().replace('-', '')

    @property
    def setting_status(self) -> typing.Optional[str]:
        """
        Return the status of the Release from settings.

        Return the Release's status setting from the config. For example, if the release is f30,
        this will return the value of f30.status from the config file.

        Note: This is not the same as Release.state.

        Returns:
            The status of the release.
        """
        return config.get(f'{self.setting_prefix}.status', None)

    def get_testing_side_tag(self, from_tag: str) -> str:
        """
        Return the testing side tag for this ``Release``.

        Args:
            from_tag: Name of side tag from which ``Update`` was created.

        Returns:
            Testing side tag used in koji.
        """
        side_tag_postfix = config.get(
            f'{self.setting_prefix}.koji-testing-side-tag', "-testing-pending")
        return from_tag + side_tag_postfix

    def get_pending_signing_side_tag(self, from_tag: str) -> str:
        """
        Return the testing side tag for this ``Release``.

        Args:
            from_tag: Name of side tag from which ``Update`` was created.

        Returns:
            Testing side tag used in koji.
        """
        side_tag_postfix = config.get(
            f'{self.setting_prefix}.koji-signing-pending-side-tag', "-signing-pending")
        return from_tag + side_tag_postfix
