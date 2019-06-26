# Copyright (c) 2019 Red Hat, Inc.
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
Add from_tag column to updates.

Revision ID: d3f8bd499ecd
Revises: c60d95eef4f1
Create Date: 2019-05-14 15:10:54.769789
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3f8bd499ecd'
down_revision = 'c60d95eef4f1'


def upgrade():
    """Add the from_tag column to the updates table."""
    op.add_column('updates', sa.Column('from_tag', sa.UnicodeText(), nullable=True))


def downgrade():
    """Drop the from_tag column from the updates table."""
    op.drop_column('updates', 'from_tag')
