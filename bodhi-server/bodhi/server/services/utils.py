# Copyright © 2011-2017 Red Hat, Inc. and others.
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
"""Define utilities for service modules."""

from sqlalchemy import func, literal_column

def count_query(query):
    """
    Return the number of results the query will provide.

    Args:
        query (sqlalchemy.orm.Query): The sqlalchemy query object.
    Returns:
        int: The number of results returned
    """
    ONE = literal_column("1")
    counter = query.statement.with_only_columns(func.count(ONE))
    counter = counter.order_by(None)
    return query.session.execute(counter).scalar()
