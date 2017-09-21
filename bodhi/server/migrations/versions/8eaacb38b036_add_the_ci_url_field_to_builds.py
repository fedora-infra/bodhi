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
Add the ci_url field to builds.

Revision ID: 8eaacb38b036
Revises: 4b357c65441e
Create Date: 2017-05-18 12:01:20.698762
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8eaacb38b036'
down_revision = '4b357c65441e'


def upgrade():
    """Add the ci_url to builds."""
    op.add_column(
        'builds',
        sa.Column('ci_url', sa.UnicodeText, nullable=True)
    )


def downgrade():
    """Remove the ci_url from builds."""
    op.drop_column('builds', 'ci_url')
