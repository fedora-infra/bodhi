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
"""Bodhi's compose models."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import relationship

from bodhi.server import log
from bodhi.server.models import Base, ComposeState, UpdateRequest, UpdateType


class Compose(Base):
    """
    Express the status of an in-progress compose job.

    This object is used in a few ways:

        * It ensures that only one compose process runs per repo, serving as a compose "lock".
        * It marks which updates are part of a compose, serving as an update "lock".
        * It gives the compose process a place to log which step it is in, which will allow us to
          provide compose monitoring tools.

    Attributes:
        __exclude_columns__ (tuple): A tuple of columns to exclude when __json__() is called.
        __include_extras__ (tuple): A tuple of attributes to add when __json__() is called.
        __tablename__ (str): The name of the table in the database.
        checkpoints (str): A JSON serialized object describing the checkpoints the composer has
            reached.
        date_created (datetime.datetime): The time this Compose was created.
        error_message (str): An error message indicating what happened if the Compose failed.
        id (None): We don't want the superclass's primary key since we will use a natural primary
            key for this model.
        release_id (int): The primary key of the :class:`Release` that is being composed. Forms half
            of the primary key, with the other half being the ``request``.
        request (UpdateRequest): The request of the release that is being composed. Forms half of
            the primary key, with the other half being the ``release_id``.
        release (Release): The release that is being composed.
        state_date (datetime.datetime): The time of the most recent change to the state attribute.
        state (ComposeState): The state of the compose.
        updates (sqlalchemy.orm.collections.InstrumentedList): An iterable of updates included in
            this compose.
    """

    __exclude_columns__ = ('updates')
    # We need to include content_type and security so the composer can collate the Composes and so
    # it can pick the right composer class to use.
    __include_extras__ = ('content_type', 'security', 'update_summary')
    __tablename__ = 'composes'

    # These together form the primary key.
    release_id = Column(Integer, ForeignKey('releases.id'), primary_key=True, nullable=False)
    request = Column(UpdateRequest.db_type(), primary_key=True, nullable=False)

    # The parent class gives us an id primary key, but we'd rather have a "natural" primary key, so
    # let's override it and set to None.
    id = None
    # We could use the JSON type here, but that would require PostgreSQL >= 9.2.0. We don't really
    # need the ability to query inside this so the JSONB type probably isn't useful.
    checkpoints = Column(UnicodeText, nullable=False, default='{}')
    error_message = Column(UnicodeText)
    date_created = Column(DateTime, nullable=False, default=datetime.utcnow)
    state_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    release = relationship('Release', backref='composes')
    state = Column(ComposeState.db_type(), nullable=False, default=ComposeState.requested)

    @property
    def content_type(self):
        """
        Return the content_type of this compose.

        Returns:
            (ContentType or None): The content type of this compose, or None if there are no
                associated :class:`Updates <Update>`.
        """
        if self.updates:
            return self.updates[0].content_type

    @classmethod
    def from_dict(cls, db, compose):
        """
        Return a :class:`Compose` instance from the given dict representation of it.

        Args:
            db (sqlalchemy.orm.session.Session): A database session to use to query for the compose.
            compose (dict): A dictionary representing the compose, in the format returned by
                :meth:`Compose.__json__`.
        Returns:
            bodhi.server.models.Compose: The requested compose instance.
        """
        return db.query(cls).filter_by(
            release_id=compose['release_id'],
            request=UpdateRequest.from_string(compose['request'])).one()

    @classmethod
    def from_updates(cls, updates):
        """
        Return a list of Compose objects to compose the given updates.

        The updates will be collated by release, request, and content type, and will be added to
        new Compose objects that match those groupings.

        Note that calling this will cause each of the updates to become locked once the transaction
        is committed.

        Args:
            updates (list): A list of :class:`Updates <Update>` that you wish to Compose.
        Returns:
            list: A list of new compose objects for the given updates.
        """
        work = {}
        for update in updates:
            if not update.request:
                log.info('%s request was revoked', update.alias)
                continue
            # ASSUMPTION: For now, updates can only be of a single type.
            ctype = None
            if not update.builds:
                log.info(f"No builds in {update.alias}. Skipping.")
                continue
            for build in update.builds:
                if ctype is None:
                    ctype = build.type
                elif ctype is not build.type:  # pragma: no cover
                    # This branch is not covered because the Update.validate_builds validator
                    # catches the same assumption breakage. This check here is extra for the
                    # time when someone adds multitype updates and forgets to update this.
                    raise ValueError(f'Builds of multiple types found in {update.alias}')
            # This key is just to insert things in the same place in the "work"
            # dict.
            key = '%s-%s' % (update.release.name, update.request.value)
            if key not in work:
                work[key] = cls(request=update.request, release_id=update.release.id,
                                release=update.release)
            # Lock the Update. This implicitly adds it to the Compose because the Update.compose
            # relationship joins on the Compose's compound pk for locked Updates.
            update.locked = True

        # We cast to a list here because a dictionary's values() method does not return a list in
        # Python 3 and the docblock states that a list is returned.
        return list(work.values())

    @property
    def security(self):
        """
        Return whether this compose is a security related compose or not.

        Returns:
            bool: ``True`` if any of the :class:`Updates <Update>` in this compose are marked as
                security updates.
        """
        for update in self.updates:
            if update.type is UpdateType.security:
                return True
        return False

    @staticmethod
    def update_state_date(target, value, old, initiator):
        """
        Update the ``state_date`` when the state changes.

        Args:
            target (Compose): The compose that has had a change to its state attribute.
            value (EnumSymbol): The new value of the state.
            old (EnumSymbol): The old value of the state
            initiator (sqlalchemy.orm.attributes.Event): The event object that is initiating this
                transition.
        """
        if value != old:
            target.state_date = datetime.utcnow()

    @property
    def update_summary(self):
        """
        Return a summary of the updates attribute, suitable for transmitting via the API.

        Returns:
            list: A list of dictionaries with keys 'alias' and 'title', indexing each update alias
                and title associated with this Compose.
        """
        return [{'alias': u.alias,
                'title': u.get_title(nvr=True, beautify=True)} for u in self.updates]

    def __json__(self, request=None, exclude=None, include=None, composer=False):
        """
        Serialize this compose in JSON format.

        Args:
            request (pyramid.request.Request or None): The current web request, or None.
            exclude (iterable or None): See superclass docblock.
            include (iterable or None): See superclass docblock.
            composer (bool): If True, increase the number of excluded attributes so that only the
                attributes required by the Composer to identify Composes are included. Defaults to
                False. If used, overrides exclude and include.
        Returns:
            str: A JSON representation of the Compose.
        """
        if composer:
            exclude = ('checkpoints', 'error_message', 'date_created', 'state_date', 'release',
                       'state', 'updates')
            # We need to include content_type and security so the composer can collate the Composes
            # and so it can pick the right composer class to use.
            include = ('content_type', 'security')
        return super(Compose, self).__json__(request=request, exclude=exclude, include=include)

    def __lt__(self, other):
        """
        Return ``True`` if this compose has a higher priority than the other.

        Args:
            other (Compose): Another compose we are comparing this compose to for sorting.
        Return:
            bool: ``True`` if this compose has a higher priority than the other, else ``False``.
        """
        if self.security and not other.security:
            return True
        if other.security and not self.security:
            return False
        if self.request == UpdateRequest.stable and other.request != UpdateRequest.stable:
            return True
        return False

    def __str__(self):
        """
        Return a human-readable representation of this compose.

        Returns:
            str: A string to be displayed to users describing this compose.
        """
        return '<Compose: {} {}>'.format(self.release.name, self.request.description)
