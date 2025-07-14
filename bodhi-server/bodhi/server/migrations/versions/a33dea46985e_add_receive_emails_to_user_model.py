# Copyright (c) 2025 Mattia Verga
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
Add receive_emails to User model.

Revision ID: a33dea46985e
Revises: 16864f8ff395
Create Date: 2025-07-12 15:16:41.578622
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a33dea46985e'
down_revision = '16864f8ff395'


def upgrade():
    """Add the receive_emails column to User model."""
    op.add_column('users', sa.Column('receive_emails', sa.Boolean(), default=True))


def downgrade():
    """Remove the receive_emails column to User model."""
    op.drop_column('users', 'receive_emails')
