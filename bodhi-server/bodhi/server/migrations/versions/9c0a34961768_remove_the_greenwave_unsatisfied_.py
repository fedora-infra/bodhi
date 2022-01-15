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
Remove the greenwave_unsatisfied_requirements field from updates.

Revision ID: 9c0a34961768
Revises: bdf0e37ab793
Create Date: 2019-02-07 06:20:33.986578
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c0a34961768'
down_revision = 'bdf0e37ab793'


def upgrade():
    """Drop the greenwave_unsatisfied_requirements from the updates table."""
    op.drop_column('updates', 'greenwave_unsatisfied_requirements')


def downgrade():
    """Restore greenwave_unsatisfied_requirements field removed in the upgrade() function."""
    op.add_column('updates',
                  sa.Column('greenwave_unsatisfied_requirements', sa.UnicodeText(), nullable=True))
