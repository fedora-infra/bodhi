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

import transaction

from bodhi.models import Base, DBSession, Update, UpdateSeverity


engine = op.get_bind()
DBSession.configure(bind=engine)
Base.metadata.bind = engine


def upgrade():
    with transaction.manager:
        updates = DBSession.query(Update)

        for u in updates:
            if u.severity is None:
                u.severity = UpdateSeverity.unspecified


def downgrade():
    # There's really nothing to downgrade here
    pass
