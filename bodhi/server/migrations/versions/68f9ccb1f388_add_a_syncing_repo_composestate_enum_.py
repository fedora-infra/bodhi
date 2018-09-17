# Copyright (c) 2018 Mattia Verga
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
Add a syncing_repo ComposeState enum value.

Revision ID: 68f9ccb1f388
Revises: 385acbb51075
Create Date: 2018-09-19 15:51:37.962897
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '68f9ccb1f388'
down_revision = '385acbb51075'


def upgrade():
    """Add a 'syncing_repo' content type enum value in ck_compose_state."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_compose_state ADD VALUE 'syncing_repo' AFTER 'punging'")


def downgrade():
    """
    Alert user that we cannot downgrade this migration.

    PostgreSQL does not allow enum values to be removed.
    """
    raise NotImplementedError("Downgrading this migration is not supported.")
