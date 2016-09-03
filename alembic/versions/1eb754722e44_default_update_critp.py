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
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction

from bodhi.server.models import Base, Release, Update
from bodhi.server.util import get_critpath_pkgs


def upgrade():
    engine = op.get_bind()
    Base.metadata.bind = engine
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()

    critpath_pkgs = {}
    for release in db.query(Release):
        relname = release.name
        critpath_pkgs[relname] = sorted(get_critpath_pkgs(relname.lower()))

    with transaction.manager:
        updates = db.query(Update)

        for up in updates:
            for build in up.builds:
                if build.package.name in critpath_pkgs[up.release.name]:
                    up.critpath = True
                    break

            else:
                up.critpath = False


def downgrade():
    engine = op.get_bind()
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    Base.metadata.bind = engine

    with transaction.manager:
        updates = db.query(Update)

        for u in updates:
            u.critpath = None
