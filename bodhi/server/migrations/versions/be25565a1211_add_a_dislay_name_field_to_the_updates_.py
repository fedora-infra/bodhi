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
Add a display_name field to the updates table.

Revision ID: be25565a1211
Revises: 22858ba91115
Create Date: 2018-04-12 18:54:06.477866
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'be25565a1211'
down_revision = '22858ba91115'


def upgrade():
    """Add a display_name column to the updates table."""
    op.add_column('updates', sa.Column('display_name', sa.UnicodeText(), nullable=False,
                  server_default=u''))


def downgrade():
    """Drop the display_name field from the updates table."""
    op.drop_column('updates', 'display_name')
