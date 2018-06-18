# Copyright (c) 2018 Red Hat, Inc.
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
Drop uniqueness constraint on user email.

Revision ID: 39132c56a47e
Revises: 2c5d45f0c932
Create Date: 2018-06-18 14:11:37.270185
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '39132c56a47e'
down_revision = '2c5d45f0c932'


def upgrade():
    """Drop the uniqueness constraint on user.email."""
    op.drop_constraint('users_email_key', 'users', type_='unique')


def downgrade():
    """Create a uniqueness constraint on user.email."""
    op.create_unique_constraint('users_email_key', 'users', ['email'])
