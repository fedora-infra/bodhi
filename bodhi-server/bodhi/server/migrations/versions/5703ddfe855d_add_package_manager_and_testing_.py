# Copyright (c) 2019 Mattia Verga
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
Add package_manager and testing_repository columns to the Release model.

Revision ID: 5703ddfe855d
Revises: e8a059156d38
Create Date: 2019-05-05 07:05:03.434601
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '5703ddfe855d'
down_revision = 'e8a059156d38'


def upgrade():
    """Add package_manager Enum type and testing_repository string type."""
    package_manager = postgresql.ENUM('unspecified', 'dnf', 'yum', name='ck_package_manager')
    package_manager.create(op.get_bind())
    op.add_column('releases',
                  sa.Column('package_manager',
                            postgresql.ENUM('unspecified',
                                            'dnf',
                                            'yum',
                                            name='ck_package_manager'),
                            nullable=True,
                            server_default='unspecified')
                  )
    op.add_column('releases',
                  sa.Column('testing_repository',
                            sa.UnicodeText(),
                            nullable=True)
                  )
    op.alter_column('releases', 'package_manager', server_default=None)


def downgrade():
    """Drop package_manager and testing_repository."""
    op.drop_column('releases', 'testing_repository')
    op.drop_column('releases', 'package_manager')
    op.execute("DROP TYPE ck_package_manager")
