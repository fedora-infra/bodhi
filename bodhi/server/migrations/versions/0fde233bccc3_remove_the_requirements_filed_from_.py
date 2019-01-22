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
Remove the requirements filed from packages and updates tables.

Revision ID: 0fde233bccc3
Revises: 58b7919b942c
Create Date: 2019-01-24 09:00:34.533525
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0fde233bccc3'
down_revision = '58b7919b942c'


def upgrade():
    """Remove the requirements filed from packages and updates tables."""
    op.drop_column('updates', 'requirements')
    op.drop_column('packages', 'requirements')


def downgrade():
    """Restore the requirements filed in packages and updates tables."""
    op.add_column('updates', sa.Column('requirements', sa.UnicodeText(), nullable=True))
    op.add_column('packages', sa.Column('requirements', sa.UnicodeText(), nullable=True))
