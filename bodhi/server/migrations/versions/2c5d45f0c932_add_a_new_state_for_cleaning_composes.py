# Copyright (c) 2018 Red Hat, Inc.
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
Add a new state for cleaning Composes.

Revision ID: 2c5d45f0c932
Revises: be25565a1211
Create Date: 2018-06-14 14:37:13.643441
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = '2c5d45f0c932'
down_revision = 'be25565a1211'


def upgrade():
    """Add a new state to the compose_state enum for cleaning composes."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_compose_state ADD VALUE 'cleaning' AFTER 'signing_repo'")


def downgrade():
    """Raise an exception explaining that this migration cannot be reversed."""
    raise NotImplementedError('This migration cannot be reversed.')
