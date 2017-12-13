# Copyright (c) 2017 Red Hat, Inc.
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
Add container enum.

Revision ID: da710ff02641
Revises: 630acb5218a4
Create Date: 2017-12-13 02:08:07.726789
"""
from alembic import op
from sqlalchemy import exc


# revision identifiers, used by Alembic.
revision = 'da710ff02641'
down_revision = '630acb5218a4'


def upgrade():
    """Add a 'container' content type enum value in ck_content_type."""
    op.execute('COMMIT')  # See https://bitbucket.org/zzzeek/alembic/issue/123
    try:
        # This will raise a ProgrammingError if the DB server doesn't use BDR.
        op.execute('SHOW bdr.permit_ddl_locking')
        # This server uses BDR, so let's ask for a DDL lock.
        op.execute('SET LOCAL bdr.permit_ddl_locking = true')
    except exc.ProgrammingError:
        # This server doesn't use BDR, so no problem.
        pass
    op.execute("ALTER TYPE ck_content_type ADD VALUE 'container' AFTER 'module'")


def downgrade():
    """
    Alert user that we cannot downgrade this migration.

    PostgreSQL does not allow enum values to be removed.
    """
    raise NotImplementedError("Downgrading this migration is not supported.")
