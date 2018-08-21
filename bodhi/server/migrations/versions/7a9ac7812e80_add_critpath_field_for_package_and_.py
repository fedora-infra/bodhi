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
Add critpath field for package and release.

Revision ID: 7a9ac7812e80
Revises: 385acbb51075
Create Date: 2018-07-24 18:12:13.854859
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a9ac7812e80'
down_revision = '385acbb51075'


def upgrade():
    """Add relationship to store the critical path packages."""
    op.create_table('critical_path_packages_table',
                    sa.Column('package_id', sa.Integer(), nullable=False),
                    sa.Column('release_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['package_id'], ['packages.id'], ),
                    sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ))


def downgrade():
    """Drop the relationship for storing the critical path packages."""
    op.drop_table('critical_path_packages_table')
