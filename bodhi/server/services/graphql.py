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
"""Defines API endpoints related to GraphQL objects."""
from cornice import Service

graphql = Service(name='graphql', path='/graphql', description='graphql service')


@graphql.get()
def graphql_get(request):
    """
    Return "Hello World".

    Args:
        request (pyramid.Request): The current request.
    Returns:
        str: A string "Hello World".
    """
    return "Hello World"
