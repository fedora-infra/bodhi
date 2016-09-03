"""Set testing/stable dates for all old updates.

Revision ID: 3dbed75df3fe
Revises: 13cfca635b99
Create Date: 2015-09-03 14:06:11.762119

"""

# revision identifiers, used by Alembic.
revision = '3dbed75df3fe'
down_revision = '13cfca635b99'

import transaction

from alembic import op
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

from bodhi.server.models import Update, Base

import logging
log = logging.getLogger('alembic.migration')

testing = u'This update has been pushed to testing'
stable = u'This update has been pushed to stable'

def upgrade():
    log.warn("Skipping.  Do this by hand by uncommenting and running in tmux.")
    #log.info("Getting session for data upgrade.")
    #engine = op.get_bind().engine
    #Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    #Session.configure(bind=engine)
    #db = Session()
    #Base.metadata.bind = engine

    #with transaction.manager:
    #    log.info("Querying for all updates ever.")
    #    total = db.query(Update).count()
    #    log.info(" %i" % total)
    #    log.info("OK")
    #    for i, update in enumerate(db.query(Update).yield_per(1000).enable_eagerloads(False)):
    #        if i % 100 == 0:
    #            log.info(" Considering update (%i/%i) %r" % (
    #                i, total, update.title))
    #        for comment in update.comments:
    #            if comment.user.name == u'bodhi':
    #                if comment.text.startswith(testing):
    #                    update.date_testing = comment.timestamp
    #                elif comment.text.startswith(stable):
    #                    update.date_stable = comment.timestamp
    #    log.info("Done.  Committing..")


def downgrade():
    # NOPE!
    pass
