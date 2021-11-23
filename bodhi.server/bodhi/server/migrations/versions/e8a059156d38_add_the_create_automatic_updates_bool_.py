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
Add the create_automatic_updates bool to Release.

Revision ID: e8a059156d38
Revises: 3a2e248d1757
Create Date: 2019-05-02 15:43:06.332525
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8a059156d38'
down_revision = '3a2e248d1757'


def upgrade():
    """Add the create_automatic_updates bool column to releases."""
    op.add_column('releases', sa.Column('create_automatic_updates', sa.Boolean(), nullable=True))


def downgrade():
    """Remove the create_automatic_updates bool column from releases."""
    op.drop_column('releases', 'create_automatic_updates')
