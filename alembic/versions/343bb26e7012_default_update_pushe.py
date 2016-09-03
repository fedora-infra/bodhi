"""Default Update.pushed to False

Revision ID: 343bb26e7012
Revises: 1eb754722e44
Create Date: 2013-10-15 16:08:46.473476

"""

# revision identifiers, used by Alembic.
revision = '343bb26e7012'
down_revision = '1eb754722e44'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction

from bodhi.server.models import Base, Update


def upgrade():
    engine = op.get_bind()
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    Base.metadata.bind = engine

    with transaction.manager:
        updates = db.query(Update)

        for u in updates:
            if u.pushed is None:
                u.pushed = False


def downgrade():
    # There's really nothing to downgrade here
    pass
