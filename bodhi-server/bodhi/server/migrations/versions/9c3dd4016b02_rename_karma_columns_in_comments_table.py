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
Rename karma columns in comments table.

Revision ID: 9c3dd4016b02
Revises: 22cd873f4a1f
Create Date: 2024-06-14 13:38:37.097910
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9c3dd4016b02'
down_revision = '22cd873f4a1f'


def upgrade():
    """Rename karma columns in comments table."""
    op.alter_column('comments', 'karma', nullable=False, new_column_name='feedback')
    op.alter_column('comments', 'karma_critpath', nullable=False,
                    new_column_name='feedback_critpath')


def downgrade():
    """Bring back the 'karma' name."""
    op.alter_column('comments', 'feedback', nullable=False, new_column_name='karma')
    op.alter_column('comments', 'feedback_critpath', nullable=False,
                    new_column_name='karma_critpath')
