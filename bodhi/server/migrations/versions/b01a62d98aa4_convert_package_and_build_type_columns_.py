# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc. and others.
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
Convert type columns in the packages and builds tables to enums.

Revision ID: b01a62d98aa4
Revises: c6a5e2849ca4
Create Date: 2017-05-02 18:39:32.400198
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b01a62d98aa4'
down_revision = 'c6a5e2849ca4'

builds = sa.sql.table('builds', sa.sql.column('type', sa.Integer))
packages = sa.sql.table('packages', sa.sql.column('type', sa.Integer))


def upgrade():
    """
    Convert the type columns in the builds and packages tables from ints to enums.

    Raises:
        ValueError: This migration will fail if there are any non-RPM Packages or Builds found in
            the database.
    """
    # Make sure we only have RPM Builds.
    count = op.get_bind().execute(
        sa.select([sa.func.count()]).where(builds.c.type != 1)).fetchall()[0][0]
    if count != 0:
        raise ValueError(
            ('This migration is written to assume that all Builds in the database are RPMs, but '
             'this database has non-RPM Builds. The migration will need to be refactored to '
             'support non-RPMs.'))

    # Make sure we only have RPM Packages.
    count = op.get_bind().execute(
        sa.select([sa.func.count()]).where(packages.c.type != 1)).fetchall()[0][0]
    if count != 0:
        raise ValueError(
            ('This migration is written to assume that all Packages in the database are RPMs, but '
             'this database has non-RPM Packages. The migration will need to be refactored to '
             'support non-RPMs.'))

    # Drop the integer-based columns
    op.drop_column('builds', 'type')
    op.drop_column('packages', 'type')

    # Re-add the columns as the new enum type.
    op.execute("CREATE TYPE ck_content_type AS ENUM ('base','rpm','module')")
    op.add_column(
        'builds',
        sa.Column('type', sa.Enum('base', 'rpm', 'module', name='ck_content_type'),
                  nullable=True))
    op.add_column(
        'packages',
        sa.Column('type', sa.Enum('base', 'rpm', 'module', name='ck_content_type'),
                  nullable=True))

    # Now mark all builds and packages as RPMs again.
    op.execute(builds.update().values({'type': 'rpm'}))
    op.execute(packages.update().values({'type': 'rpm'}))

    # Finally, make the columns non-nullable.
    op.alter_column('builds', 'type', nullable=False)
    op.alter_column('packages', 'type', nullable=False)


def downgrade():
    """Convert the type columns in the builds and packages tables from enums to ints."""
    # Drop the enum-typed columns.
    op.drop_column('builds', 'type')
    op.drop_column('packages', 'type')
    # Drop the enum too.
    op.execute("DROP TYPE ck_content_type")

    # Re-add the integer-typed columns.
    op.add_column('packages', sa.Column('type', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('builds', sa.Column('type', sa.INTEGER(), autoincrement=False, nullable=True))
    # Set all objects to 1, which was used to encode RPMs.
    op.execute(builds.update().values({'type': 1}))
    op.execute(packages.update().values({'type': 1}))
    # Finally, make the columns non-nullable.
    op.alter_column('builds', 'type', nullable=False)
    op.alter_column('packages', 'type', nullable=False)
