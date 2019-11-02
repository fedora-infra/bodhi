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
"""Bodhi's user models."""

import typing

from sqlalchemy import Column, ForeignKey, Integer, Table, Unicode, UnicodeText
from sqlalchemy.orm import relationship, backref

from bodhi.server.models import Base, Comment, Update
from bodhi.server.util import avatar as get_avatar

if typing.TYPE_CHECKING:  # pragma: no cover
    import pyramid  # noqa: 401

##
#  Association tables
##

user_group_table = Table('user_group_table', Base.metadata,
                         Column('user_id', Integer, ForeignKey('users.id')),
                         Column('group_id', Integer, ForeignKey('groups.id')))


class User(Base):
    """
    A Bodhi user.

    Attributes:
        name (str): The username.
        email (str): An e-mail address for the user.
        comments (sqlalchemy.orm.dynamic.AppenderQuery): An iterable of :class:`Comments <Comment>`
            the user has written.
        updates (sqlalchemy.orm.dynamic.AppenderQuery): An iterable of :class:`Updates <Update>` the
            user has created.
        groups (sqlalchemy.orm.collections.InstrumentedList): An iterable of :class:`Groups <Group>`
            the user is a member of.
    """

    __tablename__ = 'users'
    __exclude_columns__ = ('comments', 'updates', 'buildroot_overrides')
    __include_extras__ = ('avatar', 'openid')
    __get_by__ = ('name',)

    name = Column(Unicode(64), unique=True, nullable=False)
    email = Column(UnicodeText)

    # One-to-many relationships
    comments = relationship(Comment, backref=backref('user'), lazy='dynamic')
    updates = relationship(Update, backref=backref('user'), lazy='dynamic')

    # Many-to-many relationships
    groups = relationship("Group", secondary=user_group_table, backref='users')

    def avatar(self, request: 'pyramid.request') -> typing.Union[str, None]:
        """
        Return a URL for the User's avatar, or None if request is falsey.

        Args:
            request: The current web request.
        Returns:
            A URL for the User's avatar, or None if request is falsey.
        """
        if not request:
            return None
        context = dict(request=request)
        return get_avatar(context=context, username=self.name, size=24)

    def openid(self, request: 'pyramid.request') -> str:
        """
        Return an openid identity URL.

        Args:
            request: The current web request.
        Returns:
            The openid identity URL for the User object.
        """
        if not request:
            return None
        template = request.registry.settings.get('openid_template')
        return template.format(username=self.name)


class Group(Base):
    """
    A group of users.

    Attributes:
        name (str): The name of the Group.
        users (sqlalchemy.orm.collections.InstrumentedList): An iterable of the
            :class:`Users <User>` who are in the group.
    """

    __tablename__ = 'groups'
    __get_by__ = ('name',)
    __exclude_columns__ = ('id',)

    name = Column(Unicode(64), unique=True, nullable=False)

    # users backref
