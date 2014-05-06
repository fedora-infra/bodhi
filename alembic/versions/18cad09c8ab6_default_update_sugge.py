"""Default Update.suggestion to unspecified

Revision ID: 18cad09c8ab6
Revises: 387fda7a1ff0
Create Date: 2013-10-15 17:44:04.526374

"""

# revision identifiers, used by Alembic.
revision = '18cad09c8ab6'
down_revision = '387fda7a1ff0'

from alembic import op
import sqlalchemy as sa

import transaction

from bodhi.models import Base, DBSession, Update, UpdateSuggestion


def upgrade():
    engine = op.get_bind()
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine

    with transaction.manager:
        updates = DBSession.query(Update)

        for u in updates:
            if u.suggest is None:
                u.suggest = UpdateSuggestion.unspecified


def downgrade():
    # There's really nothing to downgrade here
    pass
