# Copyright (c) 2019 Sebastian Wojciechowski.
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
Remove the ci_url field from builds.

Revision ID: a3580bdf5129
Revises: 8e9dc57e082d
Create Date: 2019-01-11 17:41:30.353652
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3580bdf5129'
down_revision = 'f8a44498c806'


def upgrade():
    """Remove the ci_url from builds."""
    op.drop_column('builds', 'ci_url')


def downgrade():
    """Add the ci_url to builds."""
    op.add_column(
        'builds',
        sa.Column('ci_url', sa.UnicodeText, nullable=True)
    )
