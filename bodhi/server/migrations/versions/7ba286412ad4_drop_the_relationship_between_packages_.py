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
Drop the relationship between Packages and Users.

Revision ID: 7ba286412ad4
Revises: 2fc96aa44a74
Create Date: 2019-02-16 08:36:48.665825
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7ba286412ad4'
down_revision = '2fc96aa44a74'


def upgrade():
    """Drop the user_package_table table and associations."""
    op.drop_table('user_package_table')


def downgrade():
    """Bring back the user_package_table table and associations."""
    op.create_table(
        'user_package_table',
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('package_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='user_package_table_user_id_fkey'),
        sa.ForeignKeyConstraint(['package_id'], ['packages.id'],
                                name='user_package_table_package_id_fkey'))
