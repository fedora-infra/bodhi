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
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

from bodhi.server.models import Release, Base


def upgrade():
    op.add_column('releases', sa.Column('branch', sa.Unicode(length=10)))
    op.create_unique_constraint(None, 'releases', ['branch'])

    engine = op.get_bind()
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    Base.metadata.bind = engine

    with transaction.manager:
        for release in db.query(Release).all():
            release.branch = release.name.lower()


def downgrade():
    op.drop_constraint(None, 'releases')
    op.drop_column('releases', 'branch')
