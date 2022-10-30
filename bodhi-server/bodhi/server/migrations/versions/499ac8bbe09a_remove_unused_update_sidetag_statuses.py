# Copyright (c) 2022 Mattia Verga
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
Remove unused update sidetag statuses.

Revision ID: 499ac8bbe09a
Revises: f393d006559b
Create Date: 2022-11-11 13:01:33.598903
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '499ac8bbe09a'
down_revision = 'f393d006559b'


def upgrade():
    """Remove unused side-tag update statuses.

    The 'side_tag_active' and 'side_tag_expired' update statuses were created
    when the side-tag workflow was starting, but they were never used.
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

    # These shouldn't be necessary, but let's stay safe
    op.execute("UPDATE updates SET status = 'obsolete' WHERE status = 'side_tag_active'")
    op.execute("UPDATE updates SET status = 'obsolete' WHERE status = 'side_tag_expired'")

    op.execute("ALTER TYPE ck_update_status RENAME TO ck_update_status_old")
    op.execute(
        "CREATE TYPE ck_update_status AS ENUM('testing', "
        "'obsolete', 'stable', 'unpushed', 'pending')")
    op.execute(
        "ALTER TABLE updates ALTER COLUMN status TYPE ck_update_status "
        "USING status::text::ck_update_status")
    op.execute("DROP TYPE ck_update_status_old")


def downgrade():
    """Add side-tag statuses back."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_update_status ADD VALUE 'side_tag_active' AFTER 'testing'")
    op.execute("ALTER TYPE ck_update_status ADD VALUE 'side_tag_expired' AFTER 'side_tag_active'")
