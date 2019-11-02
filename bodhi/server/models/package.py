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
"""Bodhi's package models."""

from datetime import datetime
from urllib.error import URLError

from simplemediawiki import MediaWiki
from sqlalchemy import Column, UnicodeText, UniqueConstraint
from sqlalchemy.orm import relationship, backref, validates

from bodhi.server import log, Session
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from bodhi.server.models import Base, ContentType, TestCase
from bodhi.server.util import header, pagure_api_get


class Package(Base):
    """
    This model represents a package.

    This model uses single-table inheritance to allow for different package types.

    Attributes:
        name (str): A text string that uniquely identifies the package.
        requirements (str): A text string that lists space-separated taskotron test
            results that must pass for this package
        type (int): The polymorphic identity column. This is used to identify what Python
            class to create when loading rows from the database.
        builds (sqlalchemy.orm.collections.InstrumentedList): A list of :class:`Build` objects.
        test_cases (sqlalchemy.orm.collections.InstrumentedList): A list of :class:`TestCase`
            objects.
    """

    __tablename__ = 'packages'
    __get_by__ = ('name',)
    __exclude_columns__ = ('id', 'test_cases', 'builds',)

    name = Column(UnicodeText, nullable=False)
    requirements = Column(UnicodeText)
    type = Column(ContentType.db_type(), nullable=False)

    builds = relationship('Build', backref=backref('package', lazy='joined'))
    test_cases = relationship('TestCase', backref='package', order_by="TestCase.id")

    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': ContentType.base,
    }

    __table_args__ = (
        UniqueConstraint('name', 'type', name='packages_name_and_type_key'),
    )

    @property
    def external_name(self):
        """
        Return the package name as it's known to external services.

        For most Packages, this is self.name.

        Returns:
            str: The name of this package.
        """
        return self.name

    def get_pkg_committers_from_pagure(self):
        """
        Pull users and groups who can commit on a package in Pagure.

        Returns a tuple with two lists:
        * The first list contains usernames that have commit access.
        * The second list contains FAS group names that have commit access.

        Raises:
            RuntimeError: If Pagure did not give us a 200 code.
        """
        pagure_url = config.get('pagure_url')
        # Pagure uses plural names for its namespaces such as "rpms" except for
        # container. Flatpaks were moved from 'modules' to 'flatpaks' - hence
        # a config setting.
        if self.type == ContentType.container:
            namespace = self.type.name
        elif self.type == ContentType.flatpak:
            namespace = config.get('pagure_flatpak_namespace')
        else:
            namespace = self.type.name + 's'
        package_pagure_url = '{0}/api/0/{1}/{2}?expand_group=1'.format(
            pagure_url.rstrip('/'), namespace, self.external_name)
        package_json = pagure_api_get(package_pagure_url)

        committers = set()
        for access_type in ['owner', 'admin', 'commit']:
            committers = committers | set(
                package_json['access_users'][access_type])

        groups = set()
        for access_type in ['admin', 'commit']:
            for group_name in package_json['access_groups'][access_type]:
                groups.add(group_name)
                # Add to the list of committers the users in the groups
                # having admin or commit access
                committers = committers | set(
                    package_json.get(
                        'group_details', {}).get(group_name, []))

        # The first list contains usernames with commit access. The second list
        # contains FAS group names with commit access.
        return list(committers), list(groups)

    def fetch_test_cases(self, db):
        """
        Get a list of test cases for this package from the wiki.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
        Raises:
            BodhiException: When retrieving testcases from Wiki failed.
        """
        if not config.get('query_wiki_test_cases'):
            return

        start = datetime.utcnow()
        log.debug('Querying the wiki for test cases')

        wiki = MediaWiki(config.get('wiki_url'))
        cat_page = 'Category:Package %s test cases' % self.external_name

        def list_categorymembers(wiki, cat_page, limit=500):
            # Build query arguments and call wiki
            query = dict(action='query', list='categorymembers',
                         cmtitle=cat_page, cmlimit=limit)
            try:
                response = wiki.call(query)
            except URLError:
                raise BodhiException('Failed retrieving testcases from Wiki')
            members = [entry['title'] for entry in
                       response.get('query', {}).get('categorymembers', {})
                       if 'title' in entry]

            # Determine whether we need to recurse
            idx = 0
            while True:
                if idx >= len(members) or limit <= 0:
                    break
                # Recurse?
                if members[idx].startswith('Category:') and limit > 0:
                    members.extend(list_categorymembers(wiki, members[idx], limit - 1))
                    members.remove(members[idx])  # remove Category from list
                else:
                    idx += 1

            log.debug('Found the following unit tests: %s', members)
            return members

        for test in set(list_categorymembers(wiki, cat_page)):
            case = db.query(TestCase).filter_by(name=test).first()
            if not case:
                case = TestCase(name=test, package=self)
                db.add(case)
                db.flush()

        log.debug('Finished querying for test cases in %s', datetime.utcnow() - start)

    @validates('builds')
    def validate_builds(self, key, build):
        """
        Validate builds being appended to ensure they are all the same type as the Package.

        This method checks to make sure that all the builds on self.builds have their type attribute
        equal to self.type. The goal is to make sure that Builds of a specific type are only ever
        associated with Packages of the same type and vice-versa. For example, RpmBuilds should only
        ever associate with RpmPackages and never with ModulePackages.

        Args:
            key (str): The field's key, which is un-used in this validator.
            build (Build): The build object which was appended to the list
                of builds.

        Raises:
            ValueError: If the build being appended is not the same type as the package.
        """
        if build.type != self.type:
            raise ValueError(
                ("A {} Build cannot be associated with a {} Package. A Package's builds must be "
                 "the same type as the package.").format(
                     build.type.description, self.type.description))
        return build

    def __str__(self):
        """
        Return a string representation of the package.

        Returns:
            str: A string representing this package.
        """
        x = header(self.name)
        states = {'pending': [], 'testing': [], 'stable': []}
        if len(self.builds):
            for build in self.builds:
                if build.update and build.update.status.description in states:
                    states[build.update.status.description].append(
                        build.update)
        for state in states.keys():
            if len(states[state]):
                x += "\n %s Updates (%d)\n" % (state.title(),
                                               len(states[state]))
                for update in states[state]:
                    x += "    o %s\n" % update.get_title()
        del states
        return x

    @staticmethod
    def _get_name(build):
        """
        Determine the package name for a particular build.

        For most builds, this will return the RPM name, unless overridden in a specific
        subclass.

        Args:
            build (dict): Information about the build from the build system (koji).
        Returns:
            str: The Package object identifier for this build.
        """
        name, _, _ = build['nvr']
        return name

    @staticmethod
    def get_or_create(build):
        """
        Identify and return the Package instance associated with the build.

        For example, given a normal koji build, return a RpmPackage instance.
        Or, given a container, return a ContainerBuild instance.

        Args:
            build (dict): Information about the build from the build system (koji).
        Returns:
            Package: A type-specific instance of Package for the specific build requested.
        """
        base = ContentType.infer_content_class(Package, build['info'])
        name = base._get_name(build)
        package = base.query.filter_by(name=name).one_or_none()
        if not package:
            package = base(name=name)
            Session().add(package)
            Session().flush()
        return package


class ContainerPackage(Package):
    """Represents a Container package."""

    __mapper_args__ = {
        'polymorphic_identity': ContentType.container,
    }


class FlatpakPackage(Package):
    """Represents a Flatpak package."""

    __mapper_args__ = {
        'polymorphic_identity': ContentType.flatpak,
    }


class ModulePackage(Package):
    """Represents a Module package."""

    __mapper_args__ = {
        'polymorphic_identity': ContentType.module,
    }

    @property
    def external_name(self):
        """
        Return the package name as it's known to external services.

        For modules, this splits the :stream portion back off.

        Returns:
            str: The name of this module package without :stream.
        """
        return self.name.split(':')[0]

    @staticmethod
    def _get_name(build):
        """
        Determine the name:stream for a particular module build.

        Args:
            build (dict): Information about the build from the build system (koji).
        Returns:
            str: The name:stream of this module build.
        """
        name, stream, _ = build['nvr']
        return '%s:%s' % (name, stream)


class RpmPackage(Package):
    """Represents a RPM package."""

    __mapper_args__ = {
        'polymorphic_identity': ContentType.rpm,
    }
