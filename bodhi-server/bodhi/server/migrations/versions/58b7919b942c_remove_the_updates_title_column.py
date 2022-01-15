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
Remove the updates.title column.

Revision ID: 58b7919b942c
Revises: aae0d29d49b7
Create Date: 2019-02-20 17:13:01.260748
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58b7919b942c'
down_revision = 'eec610d7ab3a'


def upgrade():
    """Drop the updates.title column."""
    op.alter_column('updates', 'alias', existing_type=sa.BOOLEAN(), nullable=False)
    op.drop_index('ix_updates_title', table_name='updates')
    op.drop_column('updates', 'title')


def downgrade():
    """Bring back the updates.title column and try to guess what it should be set to."""
    op.add_column('updates', sa.Column('title', sa.TEXT(), autoincrement=False, nullable=True))
    # Set the title back to something similar to what it might have been. This isn't guaranteed to
    # be the title it was before, because we can't know what order the nvrs appeared in, but it will
    # set it to the expected format and expected set of NVRs. Single build updates should at least
    # get their old title back.
    op.execute(
        ("UPDATE updates SET title=("
         "SELECT string_agg(nvr, ' ') as title FROM ("
         "SELECT builds.nvr FROM builds WHERE update_id=updates.id ORDER BY nvr) as nvr)"))
    op.create_index('ix_updates_title', 'updates', ['title'], unique=True)
    op.alter_column('updates', 'alias', existing_type=sa.BOOLEAN(), nullable=True)
