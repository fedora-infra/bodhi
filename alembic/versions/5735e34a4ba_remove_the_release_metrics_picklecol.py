"""Remove the Release.metrics PickleCol

Revision ID: 5735e34a4ba
Revises: 6a438fe37fd
Create Date: 2014-06-16 10:06:40.082113

"""
from alembic import op
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5735e34a4ba'
down_revision = '6a438fe37fd'


def upgrade():
    op.drop_column('releases', 'metrics')


def downgrade():
    op.add_column('releases', sa.Column('metrics', postgresql.BYTEA(), autoincrement=False,
                  nullable=True))
