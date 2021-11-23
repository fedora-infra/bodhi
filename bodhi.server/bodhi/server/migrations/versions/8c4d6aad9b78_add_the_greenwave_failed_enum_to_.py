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
Add the greenwave_failed enum to TestGatingStatus.

Revision ID: 8c4d6aad9b78
Revises: 9991cf10ec50
Create Date: 2019-02-26 22:38:15.420477
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '8c4d6aad9b78'
down_revision = '9991cf10ec50'


def upgrade():
    """Add the greenwave_failed enum to ck_test_gating_status."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_test_gating_status ADD VALUE 'greenwave_failed' AFTER 'failed'")


def downgrade():
    """Remove the greenwave_failed enum from ck_test_gating_status."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute(
        ("UPDATE updates SET test_gating_status = 'failed' "
         "WHERE test_gating_status = 'greenwave_failed'"))
    op.execute("ALTER TYPE ck_test_gating_status RENAME TO ck_test_gating_status_old")
    op.execute(
        "CREATE TYPE ck_test_gating_status AS ENUM('ignored', 'queued', "
        "'running', 'passed', 'failed', 'waiting')")
    op.execute(
        "ALTER TABLE updates ALTER COLUMN test_gating_status TYPE ck_test_gating_status "
        "USING test_gating_status::text::ck_test_gating_status")
    op.execute("DROP TYPE ck_test_gating_status_old")
