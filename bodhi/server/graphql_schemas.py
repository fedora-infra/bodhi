# Copyright © 2020 Red Hat Inc., and others.
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
"""Defines schemas related to GraphQL objects."""
from graphene import relay, Field, String
from graphene_sqlalchemy import SQLAlchemyObjectType

from bodhi.server.models import Release as ReleaseModel, Update as UpdateModel


class Release(SQLAlchemyObjectType):
    """Type object representing a distribution release from bodhi.server.models like Fedora 27."""

    class Meta:
        """Allow to set different options to the class."""

        model = ReleaseModel
        interfaces = (relay.Node, )
    state = Field(String)
    package_manager = Field(String)


class Update(SQLAlchemyObjectType):
    """Type object representing an update from bodhi.server.models."""

    class Meta:
        """Allow to set different options to the class."""

        model = UpdateModel
        interfaces = (relay.Node, )
    status = Field(String)
    request = Field(String)
    date_approved = Field(String)
