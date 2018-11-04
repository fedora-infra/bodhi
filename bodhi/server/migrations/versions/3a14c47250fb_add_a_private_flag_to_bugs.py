# Copyright (c) 2018 Mattia Verga
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
Add a private flag to bugs.

Revision ID: 3a14c47250fb
Revises: 68f9ccb1f388
Create Date: 2018-11-04 14:55:57.939008
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a14c47250fb'
down_revision = '68f9ccb1f388'


def upgrade():
    """Add a new Bool column to bugs table, set default to False."""
    op.add_column('bugs', sa.Column('private', sa.Boolean(), nullable=True))
    op.execute("""UPDATE bugs SET private = FALSE""")
    op.alter_column('bugs', 'private', nullable=False)


def downgrade():
    """Just remove the new column."""
    op.drop_column('bugs', 'private')
