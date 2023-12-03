# Copyright (c) 2023 Adam Williamson
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
Remove requirements column from Build and Update.

Revision ID: 16864f8ff395
Revises: 3b34650a0cf6
Create Date: 2023-12-02 02:04:49.192890
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16864f8ff395'
down_revision = '3b34650a0cf6'


def upgrade():
    """Remove requirements columns from packages and updates."""
    op.drop_column('packages', 'requirements')
    op.drop_column('updates', 'requirements')


def downgrade():
    """Add requirements columns to packages and updates."""
    op.add_column('updates',
                  sa.Column('requirements', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('packages',
                  sa.Column('requirements', sa.TEXT(), autoincrement=False, nullable=True))
