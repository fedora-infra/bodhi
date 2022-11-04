# Copyright (c) 2022 Mattia Verga
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
Add critpath_groups to Update.

Revision ID: f393d006559b
Revises: d399493275b6
Create Date: 2022-10-10 12:08:18.583231
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f393d006559b'
down_revision = 'd399493275b6'


def upgrade():
    """Add new critpath_groups column to updates table."""
    op.add_column('updates', sa.Column('critpath_groups', sa.UnicodeText(), nullable=True))


def downgrade():
    """Remove critpath_groups column from updates table."""
    op.drop_column('updates', 'critpath_groups')
