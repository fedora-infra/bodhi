"""Set the pushed flag.

Revision ID: 2defe1107259
Revises: 70a58ae9f90
Create Date: 2015-09-11 15:39:03.656516

"""

# revision identifiers, used by Alembic.
revision = '2defe1107259'
down_revision = '70a58ae9f90'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction

import logging
log = logging.getLogger('alembic.migration')

from bodhi.server.models import Base, Update

def upgrade():
    log.warn("Skipping.  Do this by hand by uncommenting and running in tmux.")
    #log.info("Getting session for data upgrade.")
    #engine = op.get_bind().engine
    #Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    #Session.configure(bind=engine)
    #db = Session()
    #Base.metadata.bind = engine

    #with transaction.manager:
    #    log.info("Querying for all updates with pushed!=True.")
    #    query = db.query(Update).filter(Update.pushed!=True)
    #    total = query.count()
    #    log.info(" %i" % total)
    #    log.info("OK")
    #    for i, update in enumerate(query.yield_per(1000).enable_eagerloads(False)):
    #        if i % 100 == 0:
    #            log.info(" Considering update (%i/%i) %r" % (
    #                i, total, update.title))
    #        if update.date_stable or update.date_testing:
    #            update.pushed = True
    #    log.info("Done.  Committing..")


def downgrade():
    # NOPE!
    pass
