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
Remove the ci_status feature.

Revision ID: 95ce24bed77a
Revises: 33a416e03f50
Create Date: 2017-08-07 19:24:57.448750
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95ce24bed77a'
down_revision = '33a416e03f50'


def upgrade():
    """
    Remove database columns, enums, and constraints that were added as part of ci_status.

    Remove the ci_status enum and column, since ci_status has been superceded by test_gating_status.
    Then remove the scm_url field and its uniqueness constraint.
    """
    op.drop_column('builds', 'ci_status')
    op.execute("DROP TYPE ck_ci_status")
    op.drop_constraint('uq_scm_url', 'builds', type_='unique')
    op.drop_column('builds', 'scm_url')


def downgrade():
    """Restore the fields, enums, and constraints removed in the upgrade() function."""
    op.add_column('builds', sa.Column('scm_url', sa.Unicode(length=256), nullable=True))
    op.create_unique_constraint('uq_scm_url', 'builds', ['scm_url'])
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
