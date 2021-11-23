# Copyright (c) 2019 Sebastian Wojciechowski
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
Remove the greenwave_summary_string field from updates.

Revision ID: e5b3ddb35df3
Revises: 9c0a34961768
Create Date: 2019-02-16 07:02:20.196160
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5b3ddb35df3'
down_revision = '9c0a34961768'


def upgrade():
    """Drop the greenwave_summary_string column from the updates table."""
    op.drop_column('updates', 'greenwave_summary_string')


def downgrade():
    """Restore the greenwave_summary_string removed in the upgrade() function."""
    op.add_column('updates', sa.Column('greenwave_summary_string', sa.Unicode(255)))
