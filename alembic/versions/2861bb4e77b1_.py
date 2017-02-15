"""Add the stacks table.

Revision ID: 2861bb4e77b1
Revises: 5735e34a4ba
Create Date: 2014-08-08 11:45:25.303638

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2861bb4e77b1'
down_revision = '5735e34a4ba'


def upgrade():
    op.create_table(
        'stacks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.UnicodeText(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.add_column(u'packages', sa.Column('stack_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column(u'packages', 'stack_id')
    op.drop_table('stacks')
