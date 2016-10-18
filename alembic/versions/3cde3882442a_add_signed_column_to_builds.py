"""Add a signed column to the Builds model.

Revision ID: 3cde3882442a
Revises: 4df1fcd59050
Create Date: 2016-10-11 19:37:30.847965

"""

# revision identifiers, used by Alembic.
revision = '3cde3882442a'
down_revision = '4df1fcd59050'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('builds', sa.Column('signed', sa.Boolean(), nullable=True, default=False))
    builds = sa.sql.table('builds', sa.sql.column('signed', sa.Boolean))
    op.execute(
        builds.update().values({'signed': True}))
    op.alter_column('builds', column_name='signed', nullable=False)


def downgrade():
    op.drop_column('builds', 'signed')
