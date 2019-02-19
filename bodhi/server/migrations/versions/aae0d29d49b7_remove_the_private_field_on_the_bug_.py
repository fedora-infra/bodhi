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
Remove the private field on the Bug model.

Revision ID: aae0d29d49b7
Revises: 190ba571c7d2
Create Date: 2019-02-19 01:53:37.699933
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aae0d29d49b7'
down_revision = '190ba571c7d2'


def upgrade():
    """Remove the private field from the bugs table."""
    op.drop_column('bugs', 'private')


def downgrade():
    """Add the private field back to the bugs table."""
    op.add_column('bugs', sa.Column('private', sa.BOOLEAN(), autoincrement=False, nullable=True))
