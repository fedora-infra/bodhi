# Copyright (c) 2019 Sebastian Wojciechowski.
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
Remove the updates.date_approved column.

Revision ID: ecdc74e3857c
Revises: d3f8bd499ecd
Create Date: 2019-11-10 17:33:49.688578
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ecdc74e3857c'
down_revision = 'd3f8bd499ecd'


def upgrade():
    """Drop the date_approved column from the updates table."""
    op.drop_column('updates', 'date_approved')


def downgrade():
    """Restore date_approved field removed in the upgrade() function."""
    op.add_column('updates', sa.Column('date_approved', sa.DateTime, nullable=True))
