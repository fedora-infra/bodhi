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
"""Bodhi's Enums models."""

import re

from sqlalchemy.types import SchemaType, TypeDecorator, Enum

# http://techspot.zzzeek.org/2011/01/14/the-enum-recipe


class EnumSymbol(object):
    """Define a fixed symbol tied to a parent class."""

    def __init__(self, cls_, name, value, description):
        """
        Initialize the EnumSymbol.

        Args:
            cls_ (EnumMeta): The metaclass this symbol is tied to.
            name (str): The name of this symbol.
            value (str): The value used in the database to represent this symbol.
            description (str): A human readable description of this symbol.
        """
        self.cls_ = cls_
        self.name = name
        self.value = value
        self.description = description

    def __lt__(self, other):
        """
        Return True if self.value is less than other.value.

        Args:
            other (EnumSymbol): The other EnumSymbol we are being compared to.
        Returns:
            bool: True if self.value is less than other.value, False otherwise.
        """
        return self.value < other.value

    def __reduce__(self):
        """
        Allow unpickling to return the symbol linked to the DeclEnum class.

        Returns:
            tuple: A 2-tuple of the ``getattr`` function, and a 2-tuple of the EnumSymbol's member
            class and name.
        """
        return getattr, (self.cls_, self.name)

    def __iter__(self):
        """
        Iterate over this EnumSymbol's value and description.

        Returns:
            iterator: An iterator over the value and description.
        """
        return iter([self.value, self.description])

    def __repr__(self):
        """
        Return a string representation of this EnumSymbol.

        Returns:
            str: A string representation of this EnumSymbol's value.
        """
        return "<%s>" % self.name

    def __str__(self) -> str:
        """
        Return a string representation of this EnumSymbol.

        Returns:
            A string representation of this EnumSymbol's value.
        """
        return str(self.value)

    def __json__(self, request=None):
        """
        Return a JSON representation of this EnumSymbol.

        Args:
            request (pyramid.request.Request): The current request.
        Returns:
            str: A string representation of this EnumSymbol's value.
        """
        return self.value


class EnumMeta(type):
    """Generate new DeclEnum classes."""

    def __init__(cls, classname, bases, dict_):
        """
        Initialize the metaclass.

        Args:
            classname (str): The name of the enum.
            bases (list): A list of base classes for the enum.
            dict_ (dict): A key-value mapping for the new enum's attributes.
        Returns:
            DeclEnum: A new DeclEnum.
        """
        cls._reg = reg = cls._reg.copy()
        for k, v in dict_.items():
            if isinstance(v, tuple):
                sym = reg[v[0]] = EnumSymbol(cls, k, *v)
                setattr(cls, k, sym)
        return type.__init__(cls, classname, bases, dict_)

    def __iter__(cls):
        """
        Iterate the enum values.

        Returns:
            iterator: An iterator for the enum values.
        """
        return iter(cls._reg.values())


class DeclEnum(metaclass=EnumMeta):
    """Declarative enumeration."""

    _reg = {}

    @classmethod
    def from_string(cls, value):
        """
        Convert a string version of the enum to its enum type.

        Args:
            value (str): A string that you wish to convert to an Enum value.
        Returns:
            EnumSymbol: The symbol corresponding to the value.
        Raises:
            ValueError: If no symbol matches the given value.
        """
        try:
            return cls._reg[value]
        except KeyError:
            raise ValueError("Invalid value for %r: %r" % (cls.__name__, value))

    @classmethod
    def values(cls):
        """
        Return the possible values that this enum can take on.

        Returns:
            list: A list of strings of the values that this enum can represent.
        """
        return list(cls._reg.keys())

    @classmethod
    def db_type(cls):
        """
        Return a database column type to be used for this enum.

        Returns:
            DeclEnumType: A DeclEnumType to be used for this enum.
        """
        return DeclEnumType(cls)


class DeclEnumType(SchemaType, TypeDecorator):
    """A database column type for an enum."""

    def __init__(self, enum):
        """
        Initialize with the given enum.

        Args:
            enum (bodhi.server.models.EnumMeta): The enum metaclass.
        """
        self.enum = enum
        self.impl = Enum(
            *enum.values(),
            name="ck%s" % re.sub('([A-Z])', lambda m: "_" + m.group(1).lower(), enum.__name__),
            # Required for SQLAlchemy >= 1.3.8
            # https://docs.sqlalchemy.org/en/14/changelog/changelog_13.html#change-ac119f6307026142f7a0ccbf81065f25
            sort_key_function=lambda e: str(e),
        )

    def _set_table(self, table, column):
        """
        Set the table for this object.

        Args:
            table (sqlalchemy.sql.schema.Table): The table that uses this Enum.
            column (sqlalchemy.sql.schema.Column): The column that uses this Enum.
        """
        self.impl._set_table(table, column)

    def copy(self):
        """
        Return a copy of self.

        Returns:
            DeclEnumType: A copy of self.
        """
        return DeclEnumType(self.enum)

    def process_bind_param(self, value, dialect):
        """
        Return the value of the enum.

        Args:
            value (bodhi.server.models.enum.EnumSymbol): The enum symbol we are resolving the value
                of.
            dialect (sqlalchemy.engine.default.DefaultDialect): Unused.
        Returns:
            str: The EnumSymbol's value.
        """
        if value is None:
            return None
        return value.value

    def process_result_value(self, value, dialect):
        """
        Return the enum that matches the given string.

        Args:
            value (str): The name of an enum.
            dialect (sqlalchemy.engine.default.DefaultDialect): Unused.
        Returns:
            EnumSymbol or None: The enum that matches value, or ``None`` if ``value`` is ``None``.
        """
        if value is None:
            return None
        return self.enum.from_string(value.strip())

    def create(self, bind=None, checkfirst=False):
        """Issue CREATE ddl for this type, if applicable."""
        super(DeclEnumType, self).create(bind, checkfirst)
        t = self.dialect_impl(bind.dialect)
        if t.impl.__class__ is not self.__class__ and isinstance(t, SchemaType):
            t.impl.create(bind=bind, checkfirst=checkfirst)

    def drop(self, bind=None, checkfirst=False):
        """Issue DROP ddl for this type, if applicable."""
        super(DeclEnumType, self).drop(bind, checkfirst)
        t = self.dialect_impl(bind.dialect)
        if t.impl.__class__ is not self.__class__ and isinstance(t, SchemaType):
            t.impl.drop(bind=bind, checkfirst=checkfirst)


##
#  Enumerated type declarations
##
class ContentType(DeclEnum):
    """
    Used to differentiate between different kinds of content in various models.

    This enum is used to mark objects as pertaining to particular kinds of content type, such as
    RPMs or Modules.

    Attributes:
        base (EnumSymbol): This is used to represent base classes that are shared between specific
            content types.
        rpm (EnumSymbol): Used to represent RPM related objects.
        module (EnumSymbol): Used to represent Module related objects.
        container (EnumSymbol): Used to represent Container related objects.
        flatpak (EnumSymbol): Used to represent Flatpak related objects.
    """

    base = 'base', 'Base'
    rpm = 'rpm', 'RPM'
    module = 'module', 'Module'
    container = 'container', 'Container'
    flatpak = 'flatpak', 'Flatpak'

    @classmethod
    def infer_content_class(cls, base, build):
        """
        Identify and return the child class associated with the appropriate ContentType.

        For example, given the Package base class and a normal koji build, return
        the RpmPackage model class. Or, given the Build base class and a container
        build, return the ContainerBuild model class.

        Args:
            base (BodhiBase): A base model class, such as :class:`Build` or :class:`Package`.
            build (dict): Information about the build from the build system (koji).
        Returns:
            BodhiBase: The type-specific child class of base that is appropriate to use with the
            given koji build.
        """
        # Default value.  Overridden below if we find markers in the build info
        identity = cls.rpm

        extra = build.get('extra') or {}
        if 'module' in extra.get('typeinfo', {}):
            identity = cls.module
        elif 'container_koji_task_id' in extra:
            if 'flatpak' in extra['image']:
                identity = cls.flatpak
            else:
                identity = cls.container

        return base.find_polymorphic_child(identity)


class UpdateStatus(DeclEnum):
    """
    An enum used to describe the current state of an update.

    Attributes:
        pending (EnumSymbol): The update is not in any repository.
        testing (EnumSymbol): The update is in the testing repository.
        stable (EnumSymbol): The update is in the stable repository.
        unpushed (EnumSymbol): The update had been in a testing repository, but has been removed.
        obsolete (EnumSymbol): The update has been obsoleted by another update.
        side_tag_active (EnumSymbol): The update's side tag is currently active.
        side_tag_expired (EnumSymbol): The update's side tag has expired.
    """

    pending = 'pending', 'pending'
    testing = 'testing', 'testing'
    stable = 'stable', 'stable'
    unpushed = 'unpushed', 'unpushed'
    obsolete = 'obsolete', 'obsolete'
    side_tag_active = 'side_tag_active', 'Side tag active'
    side_tag_expired = 'side_tag_expired', 'Side tag expired'


class TestGatingStatus(DeclEnum):
    """
    This class lists the different status the ``Update.test_gating_status`` flag can have.

    Attributes:
        waiting (EnumSymbol): Bodhi is waiting to hear about the test gating status of the update.
        ignored (EnumSymbol): Greenwave said that the update does not require any tests.
        queued (EnumSymbol): Greenwave said that the required tests for this update have been
            queued.
        running (EnumSymbol): Greenwave said that the required tests for this update are running.
        passed (EnumSymbol): Greenwave said that the required tests for this update have passed.
        failed (EnumSymbol): Greenwave said that the required tests for this update have failed.
    """

    waiting = 'waiting', 'Waiting'
    ignored = 'ignored', 'Ignored'
    queued = 'queued', 'Queued'
    running = 'running', 'Running'
    passed = 'passed', 'Passed'
    failed = 'failed', 'Failed'
    greenwave_failed = 'greenwave_failed', 'Greenwave failed to respond'


class UpdateType(DeclEnum):
    """
    An enum used to classify the type of the update.

    Attributes:
        bugfix (EnumSymbol): The update fixes bugs only.
        security (EnumSymbol): The update addresses security issues.
        newpackage (EnumSymbol): The update introduces new packages to the release.
        enhancement (EnumSymbol): The update introduces new features.
    """

    bugfix = 'bugfix', 'bugfix'
    security = 'security', 'security'
    newpackage = 'newpackage', 'newpackage'
    enhancement = 'enhancement', 'enhancement'
    unspecified = 'unspecified', 'unspecified'


class UpdateRequest(DeclEnum):
    """
    An enum used to specify an update requesting to change states.

    Attributes:
        testing (EnumSymbol): The update is requested to change to testing.
        obsolete (EnumSymbol): The update has been obsoleted by another update.
        unpush (EnumSymbol): The update no longer needs to be released.
        revoke (EnumSymbol): The unpushed update will no longer be composed in any repository.
        stable (EnumSymbol): The update is ready to be pushed to the stable repository.
    """

    testing = 'testing', 'testing'
    obsolete = 'obsolete', 'obsolete'
    unpush = 'unpush', 'unpush'
    revoke = 'revoke', 'revoke'
    stable = 'stable', 'stable'


class UpdateSeverity(DeclEnum):
    """
    An enum used to specify the severity of the update.

    Attributes:
        unspecified (EnumSymbol): The packager has not specified a severity.
        urgent (EnumSymbol): The update is urgent.
        high (EnumSymbol): The update is high severity.
        medium (EnumSymbol): The update is medium severity.
        low (EnumSymbol): The update is low severity.
    """

    unspecified = 'unspecified', 'unspecified'
    urgent = 'urgent', 'urgent'
    high = 'high', 'high'
    medium = 'medium', 'medium'
    low = 'low', 'low'


class UpdateSuggestion(DeclEnum):
    """
    An enum used to tell the user whether they need to reboot or logout after applying an update.

    Attributes:
        unspecified (EnumSymbol): No action is needed.
        reboot (EnumSymbol): The user should reboot after applying the update.
        logout (EnumSymbol): The user should logout after applying the update.
    """

    unspecified = 'unspecified', 'unspecified'
    reboot = 'reboot', 'reboot'
    logout = 'logout', 'logout'


class ReleaseState(DeclEnum):
    """
    An enum that describes the state of a :class:`Release`.

    Attributes:
        disabled (EnumSymbol): Indicates that the release is disabled.
        pending (EnumSymbol): Indicates that the release is pending.
        frozen (EnumSymbol): Indicates that the release is frozen.
        current (EnumSymbol): Indicates that the release is current.
        archived (EnumSymbol): Indicates that the release is archived.
    """

    disabled = 'disabled', 'disabled'
    pending = 'pending', 'pending'
    frozen = 'frozen', 'frozen'
    current = 'current', 'current'
    archived = 'archived', 'archived'


class ComposeState(DeclEnum):
    """
    Define the various states that a :class:`Compose` can be in.

    Attributes:
        requested (EnumSymbol): A compose has been requested, but it has not started yet.
        pending (EnumSymbol): The request for the compose has been received by the backend worker,
            but the compose has not started yet.
        initializing (EnumSymbol): The compose is initializing.
        updateinfo (EnumSymbol): The updateinfo.xml is being generated.
        punging (EnumSymbol): A Pungi soldier has been deployed to deal with the situation.
        syncing_repo (EnumSymbol): The repo is being synced to the master mirror.
        notifying (EnumSymbol): Pungi has finished successfully, and we are now sending out various
            forms of notifications, such as e-mail, bus messages, and bugzilla.
        success (EnumSymbol): The Compose has completed successfully.
        failed (EnumSymbol): The compose has failed, abandon hope.
        signing_repo (EnumSymbol): Waiting for the repo to be signed.
        cleaning (EnumSymbol): Cleaning old Composes after successful completion.
    """

    requested = 'requested', 'Requested'
    pending = 'pending', 'Pending'
    initializing = 'initializing', 'Initializing'
    updateinfo = 'updateinfo', 'Generating updateinfo.xml'
    punging = 'punging', 'Waiting for Pungi to finish'
    syncing_repo = 'syncing_repo', 'Wait for the repo to hit the master mirror'
    notifying = 'notifying', 'Sending notifications'
    success = 'success', 'Success'
    failed = 'failed', 'Failed'
    signing_repo = 'signing_repo', 'Signing repo'
    cleaning = 'cleaning', 'Cleaning old composes'


class PackageManager(DeclEnum):
    """
    An enum used to specify what package manager is used by a specific Release.

    Attributes:
        unspecified (EnumSymbol): for releases where the package manager is not specified.
        dnf (EnumSymbol): DNF package manager.
        yum (EnumSymbol): YUM package manager.
    """

    unspecified = 'unspecified', 'package manager not specified'
    dnf = 'dnf', 'dnf'
    yum = 'yum', 'yum'
