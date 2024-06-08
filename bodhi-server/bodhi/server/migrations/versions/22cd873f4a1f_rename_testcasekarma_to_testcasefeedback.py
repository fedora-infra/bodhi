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
rename TestCaseKarma to TestCaseFeedback.

Revision ID: 22cd873f4a1f
Revises: 407335e56ccb
Create Date: 2024-06-07 15:54:59.468953
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '22cd873f4a1f'
down_revision = '407335e56ccb'


def upgrade():
    """
    Rename TestCaseFeedback karma column to feedback.

    We don't need to rename the table since it is named 'comment_testcase_assoc'
    """
    op.alter_column('comment_testcase_assoc', 'karma', nullable=False, new_column_name='feedback')


def downgrade():
    """Bring back the 'karma' name."""
    op.alter_column('comment_testcase_assoc', 'feedback', nullable=False, new_column_name='karma')
