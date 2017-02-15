"""Add column date_locked to Update table

Revision ID: 3c72757fa59e
Revises: 3aae6532b560
Create Date: 2016-05-15 11:33:14.849331

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c72757fa59e'
down_revision = 'a1d8dae7cc'


def upgrade():
    op.add_column('updates', sa.Column('date_locked', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('updates', 'date_locked')
