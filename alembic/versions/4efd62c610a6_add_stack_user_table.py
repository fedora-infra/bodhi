"""Add stack_user_table and stack_group_table

Revision ID: 4efd62c610a6
Revises: d58f9439269
Create Date: 2014-10-06 13:10:55.002150

"""

# revision identifiers, used by Alembic.
revision = '4efd62c610a6'
down_revision = 'd58f9439269'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('stack_group_table',
        sa.Column('stack_id', sa.Integer(), nullable=True),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
        sa.ForeignKeyConstraint(['stack_id'], ['stacks.id'], )
    )
    op.create_table('stack_user_table',
        sa.Column('stack_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['stack_id'], ['stacks.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], )
    )


def downgrade():
    op.drop_table('stack_user_table')
    op.drop_table('stack_group_table')
