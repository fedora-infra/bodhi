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
Add packages type constraint.

Revision ID: 74cfbc6116ad
Revises: 95ce24bed77a
Create Date: 2017-11-21 19:52:30.058663
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '74cfbc6116ad'
down_revision = '95ce24bed77a'


def upgrade():
    """Create a uniqueness constraint on packages.{name,type}."""
    op.create_unique_constraint('packages_name_and_type_key', 'packages', ['name', 'type'])


def downgrade():
    """Drop the uniqueness constraint on packages.{name,type}."""
    op.drop_constraint('packages_name_and_type_key', 'packages', type_='unique')
