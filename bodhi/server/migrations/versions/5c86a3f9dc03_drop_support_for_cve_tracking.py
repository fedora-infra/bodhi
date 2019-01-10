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
Drop support for CVE tracking.

Revision ID: 5c86a3f9dc03
Revises: 8e9dc57e082d
Create Date: 2019-01-10 12:20:05.261652
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c86a3f9dc03'
down_revision = 'a418acf470f8'


def upgrade():
    """Drop the cves table and related association tables."""
    op.drop_table('update_cve_table')
    op.drop_table('bug_cve_table')
    op.drop_table('cves')


def downgrade():
    """Recreate the cves table and related association tables."""
    op.create_table(
        'cves',
        sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('cves_id_seq'::regclass)"),
                  autoincrement=True, nullable=False),
        sa.Column('cve_id', sa.VARCHAR(length=13), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint('id', name='cves_pkey'),
        sa.UniqueConstraint('cve_id', name='cves_cve_id_key'),
        postgresql_ignore_search_path=False)
    op.create_table(
        'bug_cve_table',
        sa.Column('bug_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('cve_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['bug_id'], ['bugs.id'], name='bug_cve_table_bug_id_fkey'),
        sa.ForeignKeyConstraint(['cve_id'], ['cves.id'], name='bug_cve_table_cve_id_fkey'))
    op.create_table(
        'update_cve_table',
        sa.Column('update_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('cve_id', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['cve_id'], ['cves.id'], name='update_cve_table_cve_id_fkey'),
        sa.ForeignKeyConstraint(['update_id'], ['updates.id'],
                                name='update_cve_table_update_id_fkey'))
