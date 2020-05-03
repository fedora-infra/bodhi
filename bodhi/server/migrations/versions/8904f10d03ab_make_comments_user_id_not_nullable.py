# Copyright (c) 2020 Mattia Verga
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
Make comments.user_id not nullable.

Revision ID: 8904f10d03ab
Revises: ff834fa4f23e
Create Date: 2020-05-09 13:39:38.513106
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8904f10d03ab'
down_revision = 'ff834fa4f23e'


def upgrade():
    """Make comments.user_id not nullable so as to use inner joins."""
    op.alter_column('comments', 'user_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)


def downgrade():
    """Revert back comments.user_id to be nullable."""
    op.alter_column('comments', 'user_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)
