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
Mark the bugs.private field as nullable.

Revision ID: 9991cf10ec50
Revises: d986618207bc
Create Date: 2019-02-19 15:54:53.058707
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9991cf10ec50'
down_revision = 'd986618207bc'


def upgrade():
    """Set the bugs.private column to be nullable."""
    op.alter_column('bugs', 'private', nullable=True)


def downgrade():
    """Set the bugs.private column to be non-nullable."""
    op.execute("""UPDATE bugs SET private = FALSE WHERE private = NULL""")
    op.alter_column('bugs', 'private', nullable=False)
