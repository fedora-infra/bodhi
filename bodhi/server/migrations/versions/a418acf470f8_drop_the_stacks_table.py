# Copyright (c) 2019 Red Hat, Inc.
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
Drop the stacks table.

Revision ID: a418acf470f8
Revises: a3580bdf5129
Create Date: 2019-01-15 18:48:12.236486
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a418acf470f8'
down_revision = 'a3580bdf5129'


def upgrade():
    """Drop the stacks table and associations."""
    op.drop_constraint('packages_stack_id_fkey', 'packages', type_='foreignkey')
    op.drop_column('packages', 'stack_id')
    op.drop_table('stack_group_table')
    op.drop_table('stack_user_table')
    op.drop_table('stacks')


def downgrade():
    """Bring back the stacks table and associations."""
    op.create_table(
        'stacks',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('requirements', sa.TEXT(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name='stacks_pkey'),
        sa.UniqueConstraint('name', name='stacks_name_key'))
    op.create_table(
        'stack_user_table',
        sa.Column('stack_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['stack_id'], ['stacks.id'], name='stack_user_table_stack_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='stack_user_table_user_id_fkey'))
    op.create_table(
        'stack_group_table',
        sa.Column('stack_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('group_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'],
                                name='stack_group_table_group_id_fkey'),
        sa.ForeignKeyConstraint(['stack_id'], ['stacks.id'],
                                name='stack_group_table_stack_id_fkey'))
    op.add_column('packages', sa.Column('stack_id', sa.INTEGER(), autoincrement=False,
                  nullable=True))
    op.create_foreign_key('packages_stack_id_fkey', 'packages', 'stacks', ['stack_id'], ['id'])
