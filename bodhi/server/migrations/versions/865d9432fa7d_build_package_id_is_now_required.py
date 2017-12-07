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
build.package_id is now required.

Revision ID: 865d9432fa7d
Revises: 74cfbc6116ad
Create Date: 2017-12-07 22:17:59.312908
"""
from alembic import op
import sqlalchemy as sa


revision = '865d9432fa7d'
down_revision = '74cfbc6116ad'


def upgrade():
    """Mark builds.package_id as non-nullable."""
    op.alter_column('builds', 'package_id', existing_type=sa.INTEGER(), nullable=False)


def downgrade():
    """Mark builds.package_id as nullable."""
    op.alter_column('builds', 'package_id', existing_type=sa.INTEGER(), nullable=True)
