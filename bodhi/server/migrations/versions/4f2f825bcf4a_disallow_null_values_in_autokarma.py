# -*- coding: utf-8 -*-
# Copyright © 2016 Red Hat, Inc.
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
Disallow NULL values in autokarma.

Revision ID: 4f2f825bcf4a
Revises: 06aa0e8aa5d2
Create Date: 2016-10-19 15:09:50.884185
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f2f825bcf4a'
down_revision = '06aa0e8aa5d2'


def upgrade():
    """
    Disallow NULL values in autokarma.

    Find all records with autokarma set to NULL and change them to be False, then disallow further
    NULL values.
    """
    # Build a fake mini version of the updates table so we can form an UPDATE statement.
    updates = sa.sql.table('updates', sa.sql.column('autokarma', sa.Boolean))
    # Set records with NULL autokarma to False.
    op.execute(updates.update().where(updates.c.autokarma.is_(None)).values({'autokarma': False}))
    # Finally, disallow new NULL values.
    op.alter_column('updates', 'autokarma', existing_type=sa.BOOLEAN(), nullable=False)


def downgrade():
    """
    Re-allow NULL values.

    We can't know which False's used to be NULL because that information is lost.
    """
    op.alter_column('updates', 'autokarma', existing_type=sa.BOOLEAN(), nullable=True)
