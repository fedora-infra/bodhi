"""Convert the builds table to be polymorphic.

Revision ID: 9241378c92ab
Revises: 12d3e8695f90
Create Date: 2017-04-06 20:37:24.766366
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9241378c92ab'
down_revision = '12d3e8695f90'


def upgrade():
    """Add the type column to the builds table."""
    builds = sa.sql.table('builds', sa.sql.column('type', sa.Integer()))
    op.add_column('builds', sa.Column('type', sa.Integer(), nullable=True))
    # The type 1 is the RPM Build type.
    op.execute(builds.update().values({'type': 1}))
    op.alter_column('builds', 'type', nullable=False)


def downgrade():
    """Remove the type column from the builds table."""
    op.drop_column('builds', 'type')
