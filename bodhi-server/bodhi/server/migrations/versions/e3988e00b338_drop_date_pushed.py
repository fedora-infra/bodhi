# Copyright (c) 2022 Mattia Verga
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
Drop date_pushed.

Revision ID: e3988e00b338
Revises: 499ac8bbe09a
Create Date: 2022-11-23 17:59:20.906216
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'e3988e00b338'
down_revision = '499ac8bbe09a'


def upgrade():
    """Drop date_pushed from Update model.

    date_pushed is either date_stable, date_testing or None, so we will just replace it
    with a Python property.
    """
    op.drop_column('updates', 'date_pushed')


def downgrade():
    """Re-create date_pushed.

    date_pushed will be re-set to date_stable or date_testing.
    """
    op.add_column('updates', sa.Column('date_pushed', postgresql.TIMESTAMP(),
                                       autoincrement=False, nullable=True))
    op.execute("UPDATE updates SET date_pushed = GREATEST(date_stable,date_testing)")
