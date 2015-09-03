"""Add update.date_testing/stable timestamps

Revision ID: 13cfca635b99
Revises: 52dcf7261a86
Create Date: 2015-09-02 15:55:40.940168

"""

# revision identifiers, used by Alembic.
revision = '13cfca635b99'
down_revision = '52dcf7261a86'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('updates', sa.Column('date_stable', sa.DateTime(), nullable=True))
    op.add_column('updates', sa.Column('date_testing', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('updates', 'date_testing')
    op.drop_column('updates', 'date_stable')
