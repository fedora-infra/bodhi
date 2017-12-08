# Copyright (c) 2017 Red Hat, Inc.
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
Add the new Compose model.

Revision ID: 4ed8554a4fc9
Revises: 95ce24bed77a
Create Date: 2017-11-21 20:10:08.977855
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '4ed8554a4fc9'
down_revision = '865d9432fa7d'


def upgrade():
    """Create the composes table and drop updates.date_locked."""
    op.create_table(
        'composes',
        sa.Column('checkpoints', sa.UnicodeText(), nullable=False),
        sa.Column('error_message', sa.UnicodeText(), nullable=True),
        sa.Column('date_created', sa.DateTime(), nullable=False),
        sa.Column('state_date', sa.DateTime(), nullable=False),
        sa.Column('release_id', sa.Integer(), nullable=False),
        sa.Column(
            'request',
            postgresql.ENUM('unpush', 'testing', 'revoke', 'obsolete', 'stable', 'batched',
                            name='ck_update_request', create_type=False),
            nullable=False),
        sa.Column(
            'state',
            postgresql.ENUM(
                'requested', 'pending', 'initializing', 'updateinfo', 'punging', 'notifying',
                'success', 'failed', name='ck_compose_state', create_type=True),
            nullable=False),
        sa.ForeignKeyConstraint(['release_id'], ['releases.id'], ),
        sa.PrimaryKeyConstraint('release_id', 'request'))
    op.drop_column(u'updates', 'date_locked')
    # The new Compose object uses locked Updates to form a relationship. Let's ensure no Updates are
    # locked when starting out.
    op.execute("UPDATE updates SET locked = false WHERE locked = true")


def downgrade():
    """Drop the composes table and re-create updates.date_locked."""
    op.add_column(u'updates', sa.Column('date_locked', postgresql.TIMESTAMP(), autoincrement=False,
                                        nullable=True))
    op.drop_table('composes')
    op.execute("DROP TYPE ck_compose_state")
