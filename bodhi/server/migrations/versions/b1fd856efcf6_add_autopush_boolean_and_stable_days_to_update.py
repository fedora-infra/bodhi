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
Add autotime boolean and stable_days to Update.

Revision ID: b1fd856efcf6
Revises: 5703ddfe855d
Create Date: 2019-03-22 09:51:53.941289
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1fd856efcf6'
down_revision = '5703ddfe855d'


def upgrade():
    """Add the autotime boolean and stable_days integer to the updates table."""
    # autotime
    op.add_column('updates', sa.Column('autotime', sa.Boolean()))
    op.execute('UPDATE updates SET autotime=FALSE')
    op.alter_column('updates', 'autotime', existing_type=sa.Boolean(), nullable=False)

    # stable_days
    op.add_column('updates', sa.Column('stable_days', sa.Integer()))
    op.execute('UPDATE updates SET stable_days=0')
    op.alter_column('updates', 'stable_days', existing_type=sa.Integer(), nullable=False)


def downgrade():
    """Drop the autotime boolean and the stable_days integer from the updates table."""
    op.drop_column('updates', 'autotime')
    op.drop_column('updates', 'stable_days')
