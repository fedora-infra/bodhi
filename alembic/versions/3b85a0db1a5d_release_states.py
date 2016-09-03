"""Introduce release states

Revision ID: 3b85a0db1a5d
Revises: 2519ca5cbba4
Create Date: 2014-06-02 19:50:59.299902

"""

# revision identifiers, used by Alembic.
revision = '3b85a0db1a5d'
down_revision = '2519ca5cbba4'

from alembic import op
import sqlalchemy as sa

from bodhi.server.models.models import ReleaseState


def upgrade():
    ReleaseState.db_type().create(bind=op.get_bind())
    op.add_column('releases', sa.Column('state', ReleaseState.db_type(), nullable=False, server_default='disabled'))
    op.drop_column('releases', 'locked')


def downgrade():
    op.drop_column('releases', 'state')
    op.add_column('releases', sa.Column('locked', sa.BOOLEAN(), default=False))
    ReleaseState.db_type().drop(bind=op.get_bind())
