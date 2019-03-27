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
Obsolete updates for archived release.

Revision ID: 8e9dc57e082d
Revises: 8c4d6aad9b78
Create Date: 2019-01-06 13:04:35.158562
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '8e9dc57e082d'
down_revision = '8c4d6aad9b78'


def upgrade():
    """Set archived releases updates status to 'obsolete'."""
    op.execute("UPDATE updates SET status='obsolete' WHERE release_id in \
                (SELECT id FROM releases WHERE state='archived') AND status NOT IN \
                ('unpushed', 'obsolete', 'stable')")


def downgrade():
    """Raise an exception explaining that this migration cannot be reversed."""
    raise NotImplementedError('This migration cannot be reversed.')
