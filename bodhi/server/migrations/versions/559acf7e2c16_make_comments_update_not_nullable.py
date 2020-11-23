# Copyright (c) 2020 Mattia Verga
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
Make comments.update not nullable.

Revision ID: 559acf7e2c16
Revises: 1c97477e38ee
Create Date: 2020-11-17 16:25:38.464821
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '559acf7e2c16'
down_revision = '1c97477e38ee'


def upgrade():
    """Delete orphan objects and set comments.update_id not nullable."""
    # We must drop all comments not referenced to any update
    op.execute('DELETE FROM comments WHERE update_id IS NULL')
    # Then we remove TestCaseKarma and BugKarma orphaned of their comment
    op.execute('DELETE FROM comment_bug_assoc WHERE comment_id IS NULL')
    op.execute('DELETE FROM comment_testcase_assoc WHERE comment_id IS NULL')

    op.alter_column('comments', 'update_id',
                    existing_type=sa.INTEGER(),
                    nullable=False)


def downgrade():
    """Restore comments.update_id to be nullable."""
    op.alter_column('comments', 'update_id',
                    existing_type=sa.INTEGER(),
                    nullable=True)
