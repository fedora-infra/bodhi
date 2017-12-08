# Copyright (c) 2017 Red Hat, Inc.
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
Make updates.release_id non-nullable.

Revision ID: 630acb5218a4
Revises: 74cfbc6116ad
Create Date: 2017-12-08 13:12:59.837033
"""
from alembic import op
import sqlalchemy as sa


revision = '630acb5218a4'
down_revision = '4ed8554a4fc9'


def upgrade():
    """Make updates.release_id non-nullable."""
    op.alter_column('updates', 'release_id', existing_type=sa.INTEGER(), nullable=False)


def downgrade():
    """Make updates.release_id nullable."""
    op.alter_column('updates', 'release_id', existing_type=sa.INTEGER(), nullable=True)
