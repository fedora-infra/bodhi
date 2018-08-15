# -*- coding: utf-8 -*-
# Copyright © 2016 Red Hat, Inc.
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
Drop the Update.karma column.

Revision ID: 06aa0e8aa5d2
Revises: 3cde3882442a
Create Date: 2016-10-26 16:55:54.875994
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '06aa0e8aa5d2'
down_revision = None


def upgrade():
    """Drop the karma column from the updates table."""
    op.drop_column('updates', 'karma')


def downgrade():
    """
    Downgrade is not supported.

    If we ever do want to do this for some reason, we can use the
    code from the bodhi.server.models.Update.karma() property that was written in the same
    commit that introduced this migration as a guide for how to calculate the karma column. As it is
    highly unlikely that will ever be needed, this function simply raises an Exception for now.

    Raises:
        NotImplemented: This is raised if this function is executed.
    """
    raise NotImplementedError('Downgrade not supported')
