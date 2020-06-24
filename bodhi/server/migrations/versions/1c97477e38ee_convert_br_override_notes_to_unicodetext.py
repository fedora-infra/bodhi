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
Convert buildroot override notes to unicodetext.

Revision ID: 1c97477e38ee
Revises: 325954bac9f7
Create Date: 2020-06-09 13:03:03.489398
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1c97477e38ee'
down_revision = 'f50dc199039c'


def upgrade():
    """Convert buildrootoverrides notes column to UnicodeText."""
    op.alter_column("buildroot_overrides", "notes", type_=sa.UnicodeText)


def downgrade():
    """Convert back buildrootoverrides notes column to Unicode."""
    op.alter_column("buildroot_overrides", "notes", type_=sa.Unicode)
