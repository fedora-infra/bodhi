"""Add primary keys

Revision ID: xxxxxxxxxxxxxxx
Revises: 2a10629168e4
Create Date: 2017-07-17
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'xxxxxxxxxxxxx'
down_revision = '2a10629168e4'


def upgrade():
    """ Add primary keys. """
    op.create_primary_key('pk_update_bug_table', 'update_bug_table', ['update_id', 'bug_id'])
    op.create_primary_key('pk_update_cve_table', 'update_cve_table', ['update_id', 'cve_id'])
    op.create_primary_key('pk_bug_cve_table', 'bug_cve_table', ['bug_id', 'cve_id'])
    op.create_primary_key('pk_user_package_table', 'user_package_table', ['user_id', 'package_id'])
    op.create_primary_key('pk_user_group_table', 'user_group_table', ['user_id', 'group_id'])
    op.create_primary_key('pk_stack_group_table', 'stack_group_table', ['stack_id', 'group_id'])
    op.create_primary_key('pk_stack_user_table', 'stack_user_table', ['stack_id', 'user_id'])


def downgrade():
    """ Drop primary keys. """
    op.drop_constaint('pk_update_bug_table', 'update_bug_table', 'primary')
    op.drop_constaint('pk_update_cve_table', 'update_cve_table', 'primary')
    op.drop_constaint('pk_bug_cve_table', 'bug_cve_table', 'primary')
    op.drop_constaint('pk_user_package_table', 'user_package_table', 'primary')
    op.drop_constaint('pk_user_group_table', 'user_group_table', 'primary')
    op.drop_constaint('pk_stack_group_table', 'stack_group_table', 'primary')
    op.drop_constaint('pk_stack_user_table', 'stack_user_table', 'primary')
