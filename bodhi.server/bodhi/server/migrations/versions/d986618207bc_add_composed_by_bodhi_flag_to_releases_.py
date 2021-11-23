# Copyright (c) 2018 Sebastian Wojciechowski.
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
Add composed_by_bodhi flag to releases table.

Revision ID: d986618207bc
Revises: 3a14c47250fb
Create Date: 2018-12-11 21:52:14.081423
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd986618207bc'
down_revision = ''


def upgrade():
    """Add a new composed_by_bodhi column to releases."""
    op.add_column(
        'releases', sa.Column('composed_by_bodhi', sa.Boolean(), server_default='t', default=True)
    )


def downgrade():
    """Drop the composed_by_bodhi column from the releases table."""
    op.drop_column('releases', 'composed_by_bodhi')
