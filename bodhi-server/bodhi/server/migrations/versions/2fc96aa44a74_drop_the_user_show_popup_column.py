# Copyright (c) 2019 Red Hat, Inc.
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
Drop the User.show_popup column.

Revision ID: 2fc96aa44a74
Revises: 58b7919b942c
Create Date: 2019-03-19 08:11:34.061977
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2fc96aa44a74"
down_revision = "c98beb4940b5"


def upgrade():
    """Drop the show_popups column."""
    op.drop_column("users", "show_popups")


def downgrade():
    """Re-create the show_popups column."""
    op.add_column(
        "users",
        sa.Column(
            "show_popups",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            autoincrement=False,
            nullable=True,
        ),
    )
