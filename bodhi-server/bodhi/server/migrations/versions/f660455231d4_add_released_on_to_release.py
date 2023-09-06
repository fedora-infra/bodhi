# Copyright (c) 2023 Mattia Verga
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
Add released_on to release.

Revision ID: f660455231d4
Revises: e3988e00b338
Create Date: 2023-09-06 15:33:36.185933
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f660455231d4'
down_revision = 'e3988e00b338'


def upgrade():
    """Add the released_on column."""
    op.add_column(
        'releases',
        sa.Column('released_on', sa.Date, nullable=True),
    )


def downgrade():
    """Drop the released_on column."""
    op.drop_column('releases', 'released_on')
