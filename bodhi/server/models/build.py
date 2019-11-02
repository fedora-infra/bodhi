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
"""Bodhi's build models."""

from datetime import datetime
import time

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Unicode
from sqlalchemy.orm import relationship
import rpm

from bodhi.server import buildsys, log
from bodhi.server.models import Base, ContentType
from bodhi.server.util import build_evr, get_rpm_header


class Build(Base):
    """
    This model represents a specific build of a package.

    This model uses single-table inheritance to allow for different build types.

    Attributes:
        nvr (str): The nvr field is really a mapping to the Koji build_target.name field, and is
            used to reference builds in Koji. It is named nvr in reference to the dash-separated
            name-version-release Koji name for RPMs, but it is used by other types as well. At the
            time of this writing, it was not practical to rename nvr since it is used in the REST
            API to reference builds. Thus, it should be thought of as a Koji build identifier rather
            than strictly as an RPM's name, version, and release.
        package_id (int): A foreign key to the Package that this Build is part of.
        release_id (int): A foreign key to the Release that this Build is part of.
        signed (bool): If True, this package has been signed by robosignatory. If False, it has not
            been signed yet.
        update_id (int): A foreign key to the Update that this Build is part of.
        release (sqlalchemy.orm.relationship): A relationship to the Release that this build is part
            of.
        type (ContentType): The polymorphic identify of the row. This is used by sqlalchemy to
            identify which subclass of Build to use.
    """

    __tablename__ = 'builds'
    __exclude_columns__ = ('id', 'package', 'package_id', 'release',
                           'update_id', 'update', 'override')
    __get_by__ = ('nvr',)

    nvr = Column(Unicode(100), unique=True, nullable=False)
    package_id = Column(Integer, ForeignKey('packages.id'), nullable=False)
    release_id = Column(Integer, ForeignKey('releases.id'))
    signed = Column(Boolean, default=False, nullable=False)
    update_id = Column(Integer, ForeignKey('updates.id'), index=True)

    release = relationship('Release', backref='builds', lazy=False)

    type = Column(ContentType.db_type(), nullable=False)
    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': ContentType.base,
    }

    def _get_kojiinfo(self):
        """
        Return Koji build info about this build, from a cache if possible.

        Returns:
            dict: The response from Koji's getBuild() for this Build.
        """
        if not hasattr(self, '_kojiinfo'):
            koji_session = buildsys.get_session()
            self._kojiinfo = koji_session.getBuild(self.nvr)
        return self._kojiinfo

    def _get_n_v_r(self):
        """
        Return the N, V and R components for a traditionally dash-separated build.

        Returns:
            tuple: A 3-tuple of name, version, release.
        """
        return self.nvr.rsplit('-', 2)

    @property
    def nvr_name(self):
        """
        Return the RPM name.

        Returns:
            str: The name of the Build.
        """
        return self._get_n_v_r()[0]

    @property
    def nvr_version(self):
        """
        Return the RPM version.

        Returns:
            str: The version of the Build.
        """
        return self._get_n_v_r()[1]

    @property
    def nvr_release(self):
        """
        Return the RPM release.

        Returns:
            str: The release of the Build.
        """
        return self._get_n_v_r()[2]

    def get_n_v_r(self):
        """
        Return the (name, version, release) of this build.

        Note: This does not directly return the Build's nvr attribute, which is a str.

        Returns:
            tuple: A 3-tuple representing the name, version and release from the build.
        """
        return (self.nvr_name, self.nvr_version, self.nvr_release)

    def get_tags(self, koji=None):
        """
        Return a list of koji tags for this build.

        Args:
            koji (bodhi.server.buildsys.Buildsysem or koji.ClientSession): A koji client. Defaults
                to calling bodhi.server.buildsys.get_session().
        Return:
            list: A list of strings of the Koji tags on this Build.
        """
        if not koji:
            koji = buildsys.get_session()
        return [tag['name'] for tag in koji.listTags(self.nvr)]

    def get_owner_name(self):
        """
        Return the koji username of the user who built the build.

        Returns:
            str: The username of the user.
        """
        return self._get_kojiinfo()['owner_name']

    def get_build_id(self):
        """
        Return the koji build id of the build.

        Returns:
            id: The task/build if of the build.
        """
        return self._get_kojiinfo()['id']

    def get_task_id(self) -> int:
        """
        Return the koji task id of the build.

        Returns:
            id: The task if of the build or None
        """
        return self._get_kojiinfo().get('task_id')

    def get_creation_time(self) -> datetime:
        """Return the creation time of the build."""
        return datetime.fromisoformat(self._get_kojiinfo()['creation_time'])

    def unpush(self, koji):
        """
        Move this build back to the candidate tag and remove any pending tags.

        Args:
            koji (bodhi.server.buildsys.Buildsysem or koji.ClientSession): A koji client.
        """
        log.info('Unpushing %s' % self.nvr)
        release = self.update.release
        for tag in self.get_tags(koji):
            if tag == release.pending_signing_tag:
                log.info('Removing %s tag from %s' % (tag, self.nvr))
                koji.untagBuild(tag, self.nvr)
            if tag == release.pending_testing_tag:
                log.info('Removing %s tag from %s' % (tag, self.nvr))
                koji.untagBuild(tag, self.nvr)
            if tag == release.pending_stable_tag:
                log.info('Removing %s tag from %s' % (tag, self.nvr))
                koji.untagBuild(tag, self.nvr)
            elif tag == release.testing_tag:
                log.info(
                    'Moving %s from %s to %s' % (
                        self.nvr, tag, release.candidate_tag))
                koji.moveBuild(tag, release.candidate_tag, self.nvr)

    def is_latest(self) -> bool:
        """Check if this is the latest build available in the stable tag."""
        koji_session = buildsys.get_session()
        # Get the latest builds in koji in a tag for a package
        koji_builds = koji_session.getLatestBuilds(
            self.update.release.stable_tag,
            package=self.package.name
        )

        for koji_build in koji_builds:
            build_creation_time = datetime.fromisoformat(koji_build['creation_time'])
            if self.get_creation_time() < build_creation_time:
                return False
        return True


class ContainerBuild(Build):
    """
    Represents a Container build.

    Note that this model uses single-table inheritance with its Build superclass.
    """

    __mapper_args__ = {
        'polymorphic_identity': ContentType.container,
    }


class FlatpakBuild(Build):
    """
    Represents a Flatpak build.

    Note that this model uses single-table inheritance with its Build superclass.
    """

    __mapper_args__ = {
        'polymorphic_identity': ContentType.flatpak,
    }


class ModuleBuild(Build):
    """
    Represents a Module build.

    Note that this model uses single-table inheritance with its Build superclass.

    Attributes:
        nvr (str): A unique Koji identifier for the module build.
    """

    __mapper_args__ = {
        'polymorphic_identity': ContentType.module,
    }

    @property
    def nvr_name(self):
        """
        Return the ModuleBuild's name.

        Returns:
            str: The name of the module.
        """
        return self._get_kojiinfo()['name']

    @property
    def nvr_version(self):
        """
        Return the the ModuleBuild's stream.

        Returns:
            str: The stream of the ModuleBuild.
        """
        return self._get_kojiinfo()['version']

    @property
    def nvr_release(self):
        """
        Return the ModuleBuild's version and context.

        Returns:
            str: The version of the ModuleBuild.
        """
        return self._get_kojiinfo()['release']


class RpmBuild(Build):
    """
    Represents an RPM build.

    Note that this model uses single-table inheritance with its Build superclass.

    Attributes:
        nvr (str): A dash (-) separated string of an RPM's name, version, and release (e.g.
            'bodhi-2.5.0-1.fc26')
        epoch (int): The RPM's epoch.
    """

    epoch = Column(Integer, default=0)

    __mapper_args__ = {
        'polymorphic_identity': ContentType.rpm,
    }

    @property
    def evr(self):
        """
        Return the RpmBuild's epoch, version, release, all strings in a 3-tuple.

        Return:
            tuple: (epoch, version, release)
        """
        if not self.epoch:
            self.epoch = self._get_kojiinfo()['epoch']
            if not self.epoch:
                self.epoch = 0
        return (str(self.epoch), str(self.nvr_version), str(self.nvr_release))

    def get_latest(self):
        """
        Return the nvr string of the most recent evr that is less than this RpmBuild's nvr.

        If there is no other Build, this returns ``None``.

        Returns:
            str or None: An nvr string, formatted like RpmBuild.nvr. If there is no other
                Build, returns ``None``.
        """
        koji_session = buildsys.get_session()

        # Grab a list of builds tagged with ``Release.stable_tag`` release
        # tags, and find the most recent update for this package, other than
        # this one.  If nothing is tagged for -updates, then grab the first
        # thing in ``Release.dist_tag``.  We aren't checking
        # ``Release.candidate_tag`` first, because there could potentially be
        # packages that never make their way over stable, so we don't want to
        # generate ChangeLogs against those.
        latest = None
        evr = self.evr
        for tag in [self.update.release.stable_tag, self.update.release.dist_tag]:
            builds = koji_session.getLatestBuilds(
                tag, package=self.package.name)

            # Find the first build that is older than us
            for build in builds:
                old_evr = build_evr(build)
                if rpm.labelCompare(evr, old_evr) > 0:
                    latest = build['nvr']
                    break
            if latest:
                break
        return latest

    def get_changelog(self, timelimit=0):
        """
        Retrieve the RPM changelog of this package since it's last update, or since timelimit.

        Args:
            timelimit (int): Timestamp, specified as the number of seconds since 1970-01-01 00:00:00
                UTC.
        Return:
            str: The RpmBuild's changelog.
        """
        rpm_header = get_rpm_header(self.nvr)
        descrip = rpm_header['changelogtext']
        if not descrip:
            return ""

        who = rpm_header['changelogname']
        when = rpm_header['changelogtime']

        num = len(descrip)
        if not isinstance(when, list):
            when = [when]

        str = ""
        i = 0
        while (i < num) and (when[i] > timelimit):
            try:
                str += '* %s %s\n%s\n' % (time.strftime("%a %b %e %Y",
                                          time.localtime(when[i])), who[i],
                                          descrip[i])
            except Exception:
                log.exception('Unable to add changelog entry for header %s',
                              rpm_header)
            i += 1
        return str
