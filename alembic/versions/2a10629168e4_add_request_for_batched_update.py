"""Add request for batched update

Revision ID: 2a10629168e4
Revises: 0e105f6e36b4
Create Date: 2017-06-23 22:14:55.464629
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '2a10629168e4'
down_revision = '0e105f6e36b4'


def upgrade():
    """ Add a 'batched' request enum value in ck_update_request. """
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_update_request ADD VALUE 'batched' AFTER 'stable'")


def downgrade():
    """ Alert user that we cannot downgrade this migration. """
    raise NotImplementedError("Downgrading this migration is not supported.")
