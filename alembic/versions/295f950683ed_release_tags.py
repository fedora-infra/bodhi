"""Release tags are in the DB

Revision ID: 295f950683ed
Revises: 105840e66024
Create Date: 2014-06-02 18:12:07.541496

"""

# revision identifiers, used by Alembic.
revision = '295f950683ed'
down_revision = '105840e66024'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction

from bodhi.server.models import Base, Release

def upgrade():
    engine = op.get_bind()
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    Base.metadata.bind = engine

    # Add the new columns
    op.add_column('releases', sa.Column('stable_tag', sa.UnicodeText()))
    op.add_column('releases', sa.Column('testing_tag', sa.UnicodeText()))
    op.add_column('releases', sa.Column('candidate_tag', sa.UnicodeText()))
    op.add_column('releases', sa.Column('pending_testing_tag', sa.UnicodeText()))
    op.add_column('releases', sa.Column('pending_stable_tag', sa.UnicodeText()))
    op.add_column('releases', sa.Column('override_tag', sa.UnicodeText()))

    # Add values for all releases in those new columns
    with transaction.manager:
        for r in db.query(Release):
            r.stable_tag = "%s-updates" % r.dist_tag
            r.testing_tag = "%s-testing" % r.stable_tag
            r.candidate_tag = "%s-candidate" % r.stable_tag
            r.pending_testing_tag = "%s-pending" % r.testing_tag
            r.pending_stable_tag = "%s-pending" % r.stable_tag
            r.override_tag = "%s-override" % r.dist_tag

    # Now make the new columns not-nullable
    op.alter_column('releases', 'stable_tag', nullable=False)
    op.alter_column('releases', 'testing_tag', nullable=False)
    op.alter_column('releases', 'candidate_tag', nullable=False)
    op.alter_column('releases', 'pending_testing_tag', nullable=False)
    op.alter_column('releases', 'pending_stable_tag', nullable=False)
    op.alter_column('releases', 'override_tag', nullable=False)

    # And drop the old columns
    op.drop_column('releases', '_stable_tag')
    op.drop_column('releases', '_testing_tag')
    op.drop_column('releases', '_candidate_tag')

def downgrade():
    engine = op.get_bind()
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()
    Base.metadata.bind = engine

    # Add the old columns
    op.add_column('releases', sa.Column('_stable_tag', sa.UnicodeText()))
    op.add_column('releases', sa.Column('_testing_tag', sa.UnicodeText()))
    op.add_column('releases', sa.Column('_candidate_tag', sa.UnicodeText()))

    with transaction.manager:
        for r in db.query(Release):
            r._stable_tag = r.stable_tag
            r._testing_tag = r.testing_tag
            r._candidate_tag = r.candidate_tag

    # And drop the new columns
    op.drop_column('releases', 'stable_tag')
    op.drop_column('releases', 'testing_tag')
    op.drop_column('releases', 'candidate_tag')
    op.drop_column('releases', 'pending_testing_tag')
    op.drop_column('releases', 'pending_stable_tag')
    op.drop_column('releases', 'override_tag')
