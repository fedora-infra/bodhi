"""Add the critpath column to the update model

Revision ID: 4d7508f9cabc
Revises: None
Create Date: 2013-08-12 17:59:28.477469

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d7508f9cabc'
down_revision = None


def upgrade():
    op.add_column('updates', sa.Column('critpath', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('updates', 'critpath')
