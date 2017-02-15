"""Set the pushed flag.

Revision ID: 2defe1107259
Revises: 70a58ae9f90
Create Date: 2015-09-11 15:39:03.656516

"""
import logging

from alembic import op
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import transaction

from bodhi.server.models import Base, Update


# revision identifiers, used by Alembic.
revision = '2defe1107259'
down_revision = '70a58ae9f90'

log = logging.getLogger('alembic.migration')


def upgrade():
    log.warn("Skipping.  Do this by hand by removing the return statement and running in tmux.")
    return
    log.info("Getting session for data upgrade.")
    engine = op.get_bind().engine
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    Base.metadata.bind = engine

    with transaction.manager:
        log.info("Querying for all updates with pushed!=True.")
        query = db.query(Update).filter(Update.pushed.isnot(True))
        total = query.count()
        log.info(" %i" % total)
        log.info("OK")
        for i, update in enumerate(query.yield_per(1000).enable_eagerloads(False)):
            if i % 100 == 0:
                log.info(" Considering update (%i/%i) %r" % (
                    i, total, update.title))
            if update.date_stable or update.date_testing:
                update.pushed = True
        log.info("Done.  Committing..")


def downgrade():
    raise Exception("This migration cannot be unapplied.")
