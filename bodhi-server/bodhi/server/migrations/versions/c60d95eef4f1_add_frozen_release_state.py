# Copyright (c) 2019 Sebastian Wojciechowski.
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
Add frozen release state.

Revision ID: c60d95eef4f1
Revises: b1fd856efcf6
Create Date: 2019-04-20 08:44:52.083675
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = 'c60d95eef4f1'
down_revision = 'b1fd856efcf6'


def upgrade():
    """Add frozen release state."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_release_state ADD VALUE 'frozen' AFTER 'pending'")


def downgrade():
    """Remove frozen release state."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("UPDATE releases SET state = 'pending' WHERE state = 'frozen'")
    op.execute("ALTER TYPE ck_release_state RENAME TO ck_release_state_old")
    op.execute(
        "CREATE TYPE ck_release_state AS ENUM('disabled', 'pending', "
        "'current', 'archived')")
    op.execute(
        "ALTER TABLE releases ALTER COLUMN state TYPE ck_release_state "
        "USING state::text::ck_release_state")
    op.execute("DROP TYPE ck_release_state_old")
