"""Add resultsdb requirements

Revision ID: 46f84789bec4
Revises: 4efd62c610a6
Create Date: 2014-10-29 11:48:29.622675

"""
import logging

from alembic import op
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import sqlalchemy as sa
import transaction

import bodhi.server.models as m


# revision identifiers, used by Alembic.
revision = '46f84789bec4'
down_revision = '4efd62c610a6'

log = logging.getLogger('alembic.migration')


def upgrade():
    op.add_column('packages', sa.Column('requirements', sa.UnicodeText(), nullable=True))
    op.add_column('stacks', sa.Column('requirements', sa.UnicodeText(), nullable=True))
    op.add_column('updates', sa.Column('requirements', sa.UnicodeText(), nullable=True))

    # And then, for each one, apply the defaults.
    engine = op.get_bind()
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    m.Base.metadata.bind = engine

    # We can set these requirements to whatever seems best.  I have them as the
    # only two taskotron tests I know of right now for testing, but before
    # launch we could change this to "just" depcheck, or something else.  It is
    # a policy question for FESCo, I think.  -- threebean
    default_reqs = 'depcheck upgradepath'

    with transaction.manager:
        log.info("Applying default reqs %r to all stacks." % default_reqs)
        for stack in db.query(m.Stack).all():
            stack.requirements = default_reqs

        log.info("Applying default reqs %r to all packages." % default_reqs)
        for package in db.query(m.Package).all():
            package.requirements = default_reqs

        # We don't set requirements retroactively for updates though.  That
        # would be dishonest if they had already been pushed.


def downgrade():
    op.drop_column('updates', 'requirements')
    op.drop_column('stacks', 'requirements')
    op.drop_column('packages', 'requirements')
