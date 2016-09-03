"""Default Update.severity to unspecified

Revision ID: 387fda7a1ff0
Revises: 343bb26e7012
Create Date: 2013-10-15 17:06:03.433125

"""

# revision identifiers, used by Alembic.
revision = '387fda7a1ff0'
down_revision = '343bb26e7012'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction

from bodhi.server.models import Base, Update, UpdateSeverity




def upgrade():
    engine = op.get_bind()
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    Base.metadata.bind = engine

    with transaction.manager:
        updates = db.query(Update)

        for u in updates:
            if u.severity is None:
                u.severity = UpdateSeverity.unspecified


def downgrade():
    # There's really nothing to downgrade here
    pass
