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
Remove legacy old_updateid.

Revision ID: f8a44498c806
Revises: 8e9dc57e082d
Create Date: 2019-01-11 18:34:04.277123
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a44498c806'
down_revision = '8e9dc57e082d'


def upgrade():
    """Remove database column old_updateid."""
    op.drop_column('updates', 'old_updateid')


def downgrade():
    """Restore old_updateid field removed in the upgrade() function."""
    op.add_column('updates', sa.Column('old_updateid', sa.Unicode(length=32), nullable=True))
