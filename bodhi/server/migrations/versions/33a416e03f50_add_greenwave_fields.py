# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc.
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
Add the fields for caching the Greenwave decision for each update.

Revision ID: 33a416e03f50
Revises: 2a10629168e4
Create Date: 2017-07-06 13:52:50.892504
"""
from alembic import op
from sqlalchemy import Column, Enum, Unicode


# revision identifiers, used by Alembic.
revision = '33a416e03f50'
down_revision = '2a10629168e4'


def upgrade():
    """Add two columns and an enum that are needed for Greenwave integration."""
    op.execute(
        "CREATE TYPE ck_test_gating_status AS ENUM "
        "('ignored', 'queued', 'running', 'passed', 'failed', 'waiting')")
    op.add_column(
        'updates',
        Column(
            'test_gating_status',
            Enum(
                'ignored', 'queued', 'running', 'passed', 'failed', 'waiting',
                name='ck_test_gating_status'),
            nullable=True
        )
    )
    op.add_column('updates', Column('greenwave_summary_string', Unicode(255)))


def downgrade():
    """Remove two columns and an enum that were needed for Greenwave integration."""
    op.drop_column('updates', 'test_gating_status')
    op.execute("DROP TYPE ck_test_gating_status")
    op.drop_column('updates', 'greenwave_summary_string')
