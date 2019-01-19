# Copyright (c) 2019 Sebastian Wojciechowski
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
Remove unused UpdateStatus.processing.

Revision ID: 6b3eb9ae2b87
Revises: aae0d29d49b7
Create Date: 2019-02-09 12:17:18.444588
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '6b3eb9ae2b87'
down_revision = 'aae0d29d49b7'


def upgrade():
    """Remove processing enum from the update_status enum."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("UPDATE updates SET status = 'pending' WHERE status = 'processing'")
    op.execute("ALTER TYPE ck_update_status RENAME TO ck_update_status_old")
    op.execute(
        "CREATE TYPE ck_update_status AS ENUM('testing', 'side_tag_active'"
        ", 'side_tag_expired', 'obsolete', 'stable', 'unpushed', 'pending')")
    op.execute(
        "ALTER TABLE updates ALTER COLUMN status TYPE ck_update_status "
        "USING status::text::ck_update_status")
    op.execute("DROP TYPE ck_update_status_old")


def downgrade():
    """Add processing enum to the update_status enum."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_update_status ADD VALUE 'processing' AFTER 'testing'")
