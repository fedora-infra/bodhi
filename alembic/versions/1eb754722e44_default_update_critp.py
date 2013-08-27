"""Default Update.critpath to False

Revision ID: 1eb754722e44
Revises: 4d7508f9cabc
Create Date: 2013-08-27 11:15:41.938750

"""

# revision identifiers, used by Alembic.
revision = '1eb754722e44'
down_revision = '4d7508f9cabc'

from alembic import op
import sqlalchemy as sa

import transaction

from bodhi.models import Base, DBSession, Release, Update
from bodhi.util import get_critpath_pkgs


engine = op.get_bind()
DBSession.configure(bind=engine)
Base.metadata.bind = engine


def upgrade():
    critpath_pkgs = {}
    for release in DBSession.query(Release):
        relname = release.name
        critpath_pkgs[relname] = sorted(get_critpath_pkgs(relname.lower()))

    with transaction.manager:
        updates = DBSession.query(Update)

        for up in updates:
            for build in up.builds:
                if build.package.name in critpath_pkgs[up.release.name]:
                    up.critpath = True
                    break

            else:
                up.critpath = False


def downgrade():
    with transaction.manager:
        updates = DBSession.query(Update)

        for u in updates:
            u.critpath = None
