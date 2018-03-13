# Copyright (c) 2018 Red Hat, Inc.
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
Drop the uniqueness constraint on releases.branch.

Revision ID: adee0d22d09f
Revises: 2616c86d8ac6
Create Date: 2018-03-13 20:55:03.345503
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'adee0d22d09f'
down_revision = '2616c86d8ac6'


def upgrade():
    """Drop the uniqueness constraint on releases.branch."""
    op.drop_constraint(u'releases_branch_key', 'releases', type_='unique')


def downgrade():
    """Recreate the uniqueness constraint on releases.branch."""
    op.create_unique_constraint(u'releases_branch_key', 'releases', ['branch'])
