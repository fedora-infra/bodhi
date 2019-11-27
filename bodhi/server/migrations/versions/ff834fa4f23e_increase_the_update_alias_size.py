# Copyright (c) 2019 Clément Verna
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
"""
Increase the update alias size.

Revision ID: ff834fa4f23e
Revises: d3f8bd499ecd
Create Date: 2019-11-19 18:24:14.246099
"""
from alembic import op
from sqlalchemy import Unicode


# revision identifiers, used by Alembic.
revision = 'ff834fa4f23e'
down_revision = 'd3f8bd499ecd'


def upgrade():
    """Increase the size of the updates alias column."""
    op.alter_column("updates", "alias", type_=Unicode(64))


def downgrade():
    """Brings back the size of the updates alias column to the old value."""
    op.alter_column("updates", "alias", type_=Unicode(32))
