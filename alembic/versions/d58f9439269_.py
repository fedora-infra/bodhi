"""Add a description field to the stacks

Revision ID: d58f9439269
Revises: 2861bb4e77b1
Create Date: 2014-08-21 12:50:05.920845

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd58f9439269'
down_revision = '2861bb4e77b1'


def upgrade():
    op.add_column('stacks', sa.Column('description', sa.UnicodeText(), nullable=True))


def downgrade():
    op.drop_column('stacks', 'description')
