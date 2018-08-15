# Copyright (c) 2018 Red Hat, Inc.
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
Added field to store mail template filename for releases.

Revision ID: ebaab70b2cda
Revises: 39132c56a47e
Create Date: 2018-07-09 22:04:07.451777
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ebaab70b2cda'
down_revision = '39132c56a47e'


def upgrade():
    """Add a mail_template field to the releases table."""
    op.add_column('releases', sa.Column('mail_template', sa.UnicodeText(), nullable=False,
                                        server_default='fedora_errata_template'))
    releases = sa.sql.table('releases', sa.sql.column('id_prefix', sa.String),
                            sa.sql.column('mail_template', sa.String),
                            sa.sql.column('version', sa.Integer))
    op.execute(releases.update().where(releases.c.id_prefix == "FEDORA")
                                .values({'mail_template': "fedora_errata_template"}))
    op.execute(releases.update().where(
        (releases.c.id_prefix == "FEDORA-EPEL") & (sa.cast(releases.c.version, sa.Integer()) > 7))
        .values({'mail_template': "fedora_epel_errata_template"}))
    op.execute(releases.update().where(
        (releases.c.id_prefix == "FEDORA-EPEL") & (sa.cast(releases.c.version, sa.Integer()) < 8))
        .values({'mail_template': "fedora_epel_legacy_errata_template"}))
    op.execute(releases.update().where(releases.c.id_prefix == "FEDORA-MODULAR")
                                .values({'mail_template': "fedora_modular_errata_template"}))


def downgrade():
    """Drop the mail_template field from the releases table."""
    op.drop_column('releases', 'mail_template')
