# Copyright (c) 2023 Adam Williamson
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
Update type of users.email with new Alembic.

Revision ID: 3b34650a0cf6
Revises: f660455231d4
Create Date: 2023-12-02 02:03:22.837186
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b34650a0cf6'
down_revision = 'f660455231d4'


def upgrade():
    """Change type of users.email to sa.UnicodeText."""
    op.alter_column(
        'users',
        'email',
        existing_type=sa.VARCHAR(),
        type_=sa.UnicodeText(),
        existing_nullable=True
    )


def downgrade():
    """Change type of users.email to sa.VARCHAR."""
    op.alter_column(
        'users',
        'email',
        existing_type=sa.UnicodeText(),
        type_=sa.VARCHAR(),
        existing_nullable=True
    )
