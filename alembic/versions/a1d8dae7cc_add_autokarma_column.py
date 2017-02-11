"""Add autokarma column

Revision ID: a1d8dae7cc
Revises: 3aae6532b560
Create Date: 2016-05-20 21:30:25.805859

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1d8dae7cc'
down_revision = '3aae6532b560'


def upgrade():
    op.add_column('updates', sa.Column('autokarma', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('updates', 'autokarma')
