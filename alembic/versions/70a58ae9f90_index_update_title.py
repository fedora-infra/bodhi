"""Index the Update.title and Update.date_submitted columns.

Revision ID: 70a58ae9f90
Revises: 3dbed75df3fe
Create Date: 2015-09-04 21:26:58.796325

"""

# revision identifiers, used by Alembic.
revision = '70a58ae9f90'
down_revision = '3dbed75df3fe'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index(op.f('ix_updates_title'), 'updates', ['title'], unique=False)
    op.create_index(op.f('ix_updates_date_submitted'), 'updates', ['date_submitted'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_updates_title'), table_name='updates')
    op.drop_index(op.f('ix_updates_date_submitted'), table_name='updates')
