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
Add the unspecified enum to UpdateType.

Revision ID: 3a2e248d1757
Revises: 19e28e9851a2
Create Date: 2019-04-11 11:53:15.200006
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '3a2e248d1757'
down_revision = '19e28e9851a2'


def upgrade():
    """Add the unspecified enum to ck_update_type."""
    op.execute('COMMIT')  # See https://github.com/sqlalchemy/alembic/issues/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_update_type ADD VALUE 'unspecified' AFTER 'enhancement'")


def downgrade():
    """Remove the unspecified enum from ck_update_type."""
    op.execute('COMMIT')  # See https://github.com/sqlalchemy/alembic/issues/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("UPDATE updates SET type = 'bugfix' WHERE type = 'unspecified'")
    # The more drastic option:
    # op.execute("DELETE FROM updates WHERE type = 'unspecified'")
    op.execute("ALTER TYPE ck_update_type RENAME TO ck_update_type_old")
    op.execute("CREATE TYPE ck_update_type AS ENUM('bugfix', 'security', 'newpackage', "
               "'enhancement')")
    op.execute(
        "ALTER TABLE updates ALTER COLUMN type TYPE ck_update_type "
        "USING type::text::ck_update_type")
    op.execute("DROP TYPE ck_update_type_old")
