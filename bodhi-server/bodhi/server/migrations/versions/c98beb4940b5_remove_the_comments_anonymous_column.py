# Copyright (c) 2019 Sebastian Wojciechowski
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
Remove the comments.anonymous column.

Revision ID: c98beb4940b5
Revises: 58b7919b942c
Create Date: 2019-03-17 11:55:38.248866
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c98beb4940b5'
down_revision = '58b7919b942c'


def upgrade():
    """Remove the comment's anonymous column and clear anonymous comments karma."""
    # Insert information about comment karma in comment's text
    op.execute(
        "UPDATE comments SET text=text || '\n\nkarma: +1', "
        "karma = 0 where anonymous = true and karma = 1"
    )
    op.execute(
        "UPDATE comments SET text=text || '\n\nkarma: -1', "
        "karma = 0 where anonymous = true and karma = -1"
    )
    op.drop_column('comments', 'anonymous')


def downgrade():
    """Revert the comment's anonymous column and retrieve karma from text."""
    op.add_column(
        'comments', sa.Column('anonymous', sa.BOOLEAN(), server_default='f', default=False)
    )
    op.execute(
        "update comments set anonymous = true where user_id = "
        "(select id from users where name = 'anonymous')"
    )
    # Remove information about comment karma from comment's text
    op.execute(
        "UPDATE comments SET text=REPLACE(text, '\n\nkarma: +1', ''), "
        "karma = 1 where anonymous = true and text like '%\n\nkarma: +1'"
    )
    op.execute(
        "UPDATE comments SET text=REPLACE(text, '\n\nkarma: -1', ''), "
        "karma = -1 where anonymous = true and text like '%\n\nkarma: -1'"
    )
