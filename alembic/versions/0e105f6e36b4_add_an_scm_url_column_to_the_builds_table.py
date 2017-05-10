"""Add a scm_url column to the builds table.

Revision ID: 0e105f6e36b4
Revises: 8eaacb38b036
Create Date: 2017-05-11 18:35:40.550295
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0e105f6e36b4'
down_revision = '8eaacb38b036'


def upgrade():
    """Add a scm_url column to the builds table with a uniqueness constraint."""
    op.add_column('builds', sa.Column('scm_url', sa.Unicode(length=256), nullable=True))
    op.create_unique_constraint('uq_scm_url', 'builds', ['scm_url'])


def downgrade():
    """Drop the scm_url column from the builds table and drop its uniqueness constraint."""
    op.drop_constraint('uq_scm_url', 'builds', type_='unique')
    op.drop_column('builds', 'scm_url')
