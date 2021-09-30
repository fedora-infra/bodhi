# Copyright (c) YEAR AUTHOR
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
Add the eol column.

Revision ID: d399493275b6
Revises: 559acf7e2c16
Create Date: 2021-07-27 12:53:28.303972
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd399493275b6'
down_revision = '559acf7e2c16'


def upgrade():
    """Add the eol column."""
    op.add_column(
        'releases',
        sa.Column('eol', sa.Date, nullable=True),
    )
    # ### end Alembic commands ###


def downgrade():
    """Drop the eol column."""
    op.drop_column('releases', 'eol')
