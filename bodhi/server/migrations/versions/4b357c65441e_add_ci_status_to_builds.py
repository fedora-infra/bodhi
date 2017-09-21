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
Add ci_status to builds.

Revision ID: 4b357c65441e
Revises: b01a62d98aa4
Create Date: 2017-05-11 20:13:41.879435
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b357c65441e'
down_revision = 'b01a62d98aa4'


def upgrade():
    """Add the ci_status to builds with the corresponding enum."""
    op.execute(
        "CREATE TYPE ck_ci_status AS ENUM "
        "('ignored', 'queued', 'running', 'passed', 'failed', 'waiting')")

    op.add_column(
        'builds',
        sa.Column(
            'ci_status',
            sa.Enum(
                'ignored', 'queued', 'running', 'passed', 'failed', 'waiting',
                name='ck_ci_status'),
            nullable=True
        )
    )


def downgrade():
    """Remove the ci_status from builds with the corresponding enum."""
    op.drop_column('builds', 'ci_status')
    op.execute("DROP TYPE ck_ci_status")
