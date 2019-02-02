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
Disallow null values in stable_karma and unstable_karma.

Revision ID: bdf0e37ab793
Revises: 6b3eb9ae2b87
Create Date: 2019-02-08 20:19:06.389860
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bdf0e37ab793'
down_revision = '6b3eb9ae2b87'


def upgrade():
    """
    Disallow NULL values in stable_karma and unstable_karma.

    Find all records with stable_karma and unstable_karma set to NULL and change them to
    be 3(-3), then disallow further NULL values.
    """
    # Build a fake mini version of the updates table so we can form an UPDATE statement.
    updates = sa.sql.table('updates',
                           sa.sql.column('stable_karma', sa.Integer),
                           sa.sql.column('unstable_karma', sa.Integer))
    # Set records with NULL stable_karma and unstable_karma to 3 and -3.
    op.execute(updates.update().where(updates.c.stable_karma.is_(None)).values({'stable_karma': 3}))
    op.execute(
        updates.update().where(updates.c.unstable_karma.is_(None)).values({'unstable_karma': -3})
    )
    # Finally, disallow new NULL values.
    op.alter_column('updates', 'stable_karma', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('updates', 'unstable_karma', existing_type=sa.INTEGER(), nullable=False)


def downgrade():
    """Re-allow NULL values."""
    op.alter_column('updates', 'stable_karma', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('updates', 'unstable_karma', existing_type=sa.INTEGER(), nullable=True)
