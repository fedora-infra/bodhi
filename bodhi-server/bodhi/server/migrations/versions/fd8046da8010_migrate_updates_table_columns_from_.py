# Copyright (c) 2024 Mattia Verga
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
Migrate updates table columns from karma to rating.

Revision ID: fd8046da8010
Revises: 22cd873f4a1f
Create Date: 2024-06-12 09:41:09.368933
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'fd8046da8010'
down_revision = '22cd873f4a1f'


def upgrade():
    """Rename some updates columns from term karma to rating."""
    op.alter_column('updates', 'autokarma', nullable=False, new_column_name='autorating')
    op.alter_column('updates', 'stable_karma', nullable=False, new_column_name='stable_rating')
    op.alter_column('updates', 'unstable_karma', nullable=False, new_column_name='unstable_rating')


def downgrade():
    """Bring back the 'karma' name."""
    op.alter_column('updates', 'autorating', nullable=False, new_column_name='autokarma')
    op.alter_column('updates', 'stable_rating', nullable=False, new_column_name='stable_karma')
    op.alter_column('updates', 'unstable_rating', nullable=False, new_column_name='unstable_karma')
