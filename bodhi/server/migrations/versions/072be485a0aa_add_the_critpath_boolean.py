# -*- coding: utf-8 -*-
# Copyright © 2018 Red Hat, Inc.
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
Add the critpath boolean

Revision ID: 072be485a0aa
Revises: 39132c56a47e
Create Date: 2018-07-02 18:29:39.624030
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '072be485a0aa'
down_revision = '39132c56a47e'


def upgrade():
    """Add a critpath column to the packages table with a uniqueness constraint."""
    op.add_column('packages', sa.Column(
        'critpath', sa.Boolean, default=False, nullable=False, server_default='0'))


def downgrade():
    """Drop the critpath column from the packages table."""
    op.drop_column('packages', 'critpath')
