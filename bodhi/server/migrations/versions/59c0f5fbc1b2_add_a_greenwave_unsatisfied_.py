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
Add a greenwave_unsatisfied_requirements column to the updates table.

Revision ID: 59c0f5fbc1b2
Revises: c21dd18b161a
Create Date: 2018-05-01 15:37:07.346034
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '59c0f5fbc1b2'
down_revision = 'c21dd18b161a'


def upgrade():
    """Add a greenwave_unsatisfied_requirements to the updates table."""
    op.add_column('updates',
                  sa.Column('greenwave_unsatisfied_requirements', sa.UnicodeText(), nullable=True))


def downgrade():
    """Drop the greenwave_unsatisfied_requirements from the updates table."""
    op.drop_column('updates', 'greenwave_unsatisfied_requirements')
