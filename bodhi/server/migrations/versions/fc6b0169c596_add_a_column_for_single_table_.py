"""
Add a column for single-table inheritance to the packages table.

Revision ID: fc6b0169c596
Revises: 4f2f825bcf4a
Create Date: 2017-03-31 16:40:07.136469
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fc6b0169c596'
down_revision = '4f2f825bcf4a'


def upgrade():
    """Add the column used for polymorphic identity in Packages."""
    # The default of ``1`` is the RPM package type.
    op.add_column('packages', sa.Column('type', sa.Integer(), nullable=False, server_default=u'1'))
    op.alter_column('packages', 'type', server_default=None)


def downgrade():
    """Remove the column used for polymorphic identity in Packages."""
    op.drop_column('packages', 'type')
