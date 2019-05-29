# Copyright © Red Hat, Inc.
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
Index the update_id column on the comments table.

Revision ID: 19e28e9851a2
Revises: 7ba286412ad4
Create Date: 2019-04-30 22:29:42.553574
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '19e28e9851a2'
down_revision = '7ba286412ad4'


def upgrade():
    """Add an index on comments.update_id."""
    op.create_index(op.f('ix_comments_update_id'), 'comments', ['update_id'], unique=False)


def downgrade():
    """Drop the index on comments.update_id."""
    op.drop_index(op.f('ix_comments_update_id'), table_name='comments')
