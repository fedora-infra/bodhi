"""
Add a uniqueness constraint on (name, type) for the packages table.

This is necessary since sub-types of packages may have the same name.

Revision ID: c6a5e2849ca4
Revises: 9241378c92ab
Create Date: 2017-04-20 19:30:54.278981
"""
from alembic import op


revision = 'c6a5e2849ca4'
down_revision = '9241378c92ab'


def upgrade():
    """Add the new constraint on the name and type combined, then drop the name constraint."""
    op.create_unique_constraint('packages_name_and_type_key', 'packages', ['name', 'type'])
    op.drop_constraint(u'packages_name_key', 'packages', type_='unique')


def downgrade():
    """Add the new constraint on the name alone, then drop the (name, type) constraint."""
    op.create_unique_constraint(u'packages_name_key', 'packages', ['name'])
    op.drop_constraint('packages_name_and_type_key', 'packages', type_='unique')
