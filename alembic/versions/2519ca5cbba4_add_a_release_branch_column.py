"""Add a Release.branch column

Revision ID: 2519ca5cbba4
Revises: 295f950683ed
Create Date: 2014-06-03 13:15:06.129856

"""

# revision identifiers, used by Alembic.
revision = '2519ca5cbba4'
down_revision = '295f950683ed'

from alembic import op
import sqlalchemy as sa
import transaction

from bodhi.models import DBSession, Release, Base


def upgrade():
    op.add_column('releases', sa.Column('branch', sa.Unicode(length=10)))
    op.create_unique_constraint(None, 'releases', ['branch'])

    engine = op.get_bind()
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    with transaction.manager:
        for release in DBSession.query(Release).all():
            release.branch = release.name.lower()


def downgrade():
    op.drop_constraint(None, 'releases')
    op.drop_column('releases', 'branch')
