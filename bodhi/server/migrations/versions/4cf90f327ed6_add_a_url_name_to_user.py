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
Add a url_name to User.

Revision ID: 4cf90f327ed6
Revises: ff834fa4f23e
Create Date: 2020-04-13 12:00:04.155563
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4cf90f327ed6'
down_revision = 'ff834fa4f23e'


def upgrade():
    """Add a url_name column to User class."""
    op.add_column('users',
                  sa.Column('url_name',
                            sa.Unicode(length=64),
                            nullable=True)
                  )
    op.execute("UPDATE users SET url_name = REPLACE(REPLACE(name,'/','_'),'.','_')")
    op.alter_column('users', 'url_name', nullable=False)
    op.create_unique_constraint('users_url_name_fkey', 'users', ['url_name'])


def downgrade():
    """Drop url_name column to User class."""
    op.drop_constraint('users_url_name_fkey', 'users', type_='unique')
    op.drop_column('users', 'url_name')
