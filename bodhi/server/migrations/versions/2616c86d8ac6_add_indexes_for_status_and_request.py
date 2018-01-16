# -*- coding: utf-8 -*-
# Copyright © 2017 Till Maas
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
Add indexes for status and request.

Revision ID: 2616c86d8ac6
Revises: da710ff02641
Create Date: 2017-10-26 20:45:23.152139
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '2616c86d8ac6'
down_revision = 'da710ff02641'


def upgrade():
    """Add indices to the request and status columns on the update table."""
    op.create_index(op.f('ix_updates_request'), 'updates', ['request'], unique=False)
    op.create_index(op.f('ix_updates_status'), 'updates', ['status'], unique=False)


def downgrade():
    """Drop indices to the request and status columns on the update table."""
    op.drop_index(op.f('ix_updates_status'), table_name='updates')
    op.drop_index(op.f('ix_updates_request'), table_name='updates')
