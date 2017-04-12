"""Drop the unused inherited column from the builds table.

Revision ID: 12d3e8695f90
Revises: fc6b0169c596
Create Date: 2017-04-12 23:26:25.293009
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '12d3e8695f90'
down_revision = 'fc6b0169c596'


def upgrade():
    """Remove the unused inherited column from the builds table."""
    op.drop_column('builds', 'inherited')


def downgrade():
    """Add the inherited column back and set all records to False."""
    op.add_column('builds',
                  sa.Column('inherited', sa.BOOLEAN(), autoincrement=False, nullable=True))
    # Build a fake mini version of the builds table so we can form an UPDATE statement.
    builds = sa.sql.table('builds', sa.sql.column('inherited', sa.Boolean))
    # Set all records to False, since that was the default before and since there was no way to set
    # it to anything else through the API.
    op.execute(builds.update().values({'inherited': False}))
