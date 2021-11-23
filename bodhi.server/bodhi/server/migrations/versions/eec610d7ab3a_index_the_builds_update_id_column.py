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
Index the builds.update_id column.

Revision ID: eec610d7ab3a
Revises: e5b3ddb35df3
Create Date: 2019-02-20 20:18:02.474734
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'eec610d7ab3a'
down_revision = 'e5b3ddb35df3'


def upgrade():
    """Add an index on builds.update_id."""
    op.create_index(op.f('ix_builds_update_id'), 'builds', ['update_id'], unique=False)


def downgrade():
    """Drop the index on builds.update_id."""
    op.drop_index(op.f('ix_builds_update_id'), table_name='builds')
