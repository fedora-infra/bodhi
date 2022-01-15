# Copyright (c) 2020 Mattia Verga
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
Link testcases to builds.

Revision ID: 325954bac9f7
Revises: ff834fa4f23e
Create Date: 2020-05-22 16:56:05.451523
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '325954bac9f7'
down_revision = 'ff834fa4f23e'


def upgrade():
    """
    Create a new many-to-many relationship between Build and TestCase.

    Migrate existing relations between TestCase and Package to the new table.
    Finally, remove the relationship between TestCase and Package.
    """
    op.create_table('build_testcase_table',
                    sa.Column('build_id', sa.Integer(), nullable=True),
                    sa.Column('testcase_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
                    sa.ForeignKeyConstraint(['testcase_id'], ['testcases.id'], ))

    # Remove duplicated testcases and add a unique constraint on name
    # since we're using name to retrieve object from database
    # The duplicates have no feedback, so it's safe to remove them from db
    op.execute('DELETE FROM testcases '
               'WHERE testcases.name IN '
               '(SELECT name from testcases GROUP BY name HAVING count(name) > 1) '
               'AND NOT (EXISTS (SELECT 1 FROM comment_testcase_assoc '
               'WHERE testcases.id = comment_testcase_assoc.testcase_id))')
    op.create_unique_constraint('uq_testcases_name', 'testcases', ['name'])

    # Migrate existing data to the new table
    op.execute('INSERT INTO build_testcase_table '
               'SELECT DISTINCT builds.id AS builds_id, testcases.id AS testcases_id '
               'FROM builds '
               'JOIN packages ON packages.id = builds.package_id '
               'JOIN testcases ON packages.id = testcases.package_id')

    # Finally, drop the old relationship
    op.drop_constraint('testcases_package_id_fkey', 'testcases', type_='foreignkey')
    op.drop_column('testcases', 'package_id')


def downgrade():
    """Link back TestCase to Package."""
    op.add_column('testcases', sa.Column('package_id', sa.INTEGER(),
                                         autoincrement=False, nullable=True))
    op.create_foreign_key('testcases_package_id_fkey', 'testcases',
                          'packages', ['package_id'], ['id'])
    op.drop_constraint('uq_testcases_name', 'testcases', type_='unique')

    # Bring back data to the new package relationship
    op.execute('UPDATE testcases AS t '
               'SET package_id = p.pkg_id '
               'FROM ('
               'SELECT DISTINCT ON (testcases.id) testcases.id AS tc_id, packages.id AS pkg_id '
               'FROM testcases JOIN build_testcase_table '
               'ON build_testcase_table.testcase_id = testcases.id JOIN builds '
               'ON builds.id = build_testcase_table.build_id JOIN packages '
               'ON packages.id = builds.package_id WHERE TRUE) AS p '
               'WHERE t.id = p.tc_id')

    # Finally, drop the old relationship
    op.drop_table('build_testcase_table')
