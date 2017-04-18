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
    # The default of ``1`` is the RPM Build type.
    op.add_column('builds', sa.Column('type', sa.Integer(), nullable=False, server_default=u'1'))
    op.alter_column('builds', 'type', server_default=None)


def downgrade():
    """Remove the type column from the builds table."""
    op.drop_column('builds', 'type')
