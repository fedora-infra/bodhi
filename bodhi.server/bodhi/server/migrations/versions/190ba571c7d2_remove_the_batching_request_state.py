# Copyright (c) 2019 Red Hat, Inc.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
Remove the Update's batching request state.

Revision ID: 190ba571c7d2
Revises: 5c86a3f9dc03
Create Date: 2019-02-12 16:49:04.326555
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '190ba571c7d2'
down_revision = '5c86a3f9dc03'


def upgrade():
    """Remove the update's batched request state."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("UPDATE updates SET request = 'stable' WHERE request = 'batched'")
    op.execute("ALTER TYPE ck_update_request RENAME TO ck_update_request_old")
    op.execute(
        "CREATE TYPE ck_update_request AS ENUM('testing', 'obsolete', "
        "'unpush', 'revoke', 'stable')")
    op.execute(
        "ALTER TABLE updates ALTER COLUMN request TYPE ck_update_request "
        "USING request::text::ck_update_request")
    op.execute(
        "ALTER TABLE composes ALTER COLUMN request TYPE ck_update_request "
        "USING request::text::ck_update_request")
    op.execute("DROP TYPE ck_update_request_old")


def downgrade():
    """
    Bring back the update's batched request state.

    This function is not able to restore which updates were batched since that information has been
    lost.
    """
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
