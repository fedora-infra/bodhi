"""Add a Build.epoch column

Revision ID: 83c7716b12cf
Revises: 6383ec38980
Create Date: 2016-03-01 19:05:54.649231

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '83c7716b12cf'
down_revision = '6383ec38980'


def upgrade():
    op.add_column('builds', sa.Column('epoch', sa.Integer, default=0))


def downgrade():
    op.drop_column('builds', 'epoch')
