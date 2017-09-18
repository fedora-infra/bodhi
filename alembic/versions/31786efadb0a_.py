"""Add primary keys for BDR.

Revision ID: 31786efadb0a
Revises: 95ce24bed77a
Create Date: 2017-08-16 19:59:02.266116
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '31786efadb0a'
down_revision = '95ce24bed77a'


def upgrade():
    """Add primary keys needed for BDR compatibility."""
    op.create_primary_key('pk_update_bug_table', 'update_bug_table', ['update_id', 'bug_id'])
    op.create_primary_key('pk_update_cve_table', 'update_cve_table', ['update_id', 'cve_id'])
    op.create_primary_key('pk_bug_cve_table', 'bug_cve_table', ['bug_id', 'cve_id'])
    op.create_primary_key('pk_user_package_table', 'user_package_table', ['user_id', 'package_id'])
    op.create_primary_key('pk_user_group_table', 'user_group_table', ['user_id', 'group_id'])
    op.create_primary_key('pk_stack_group_table', 'stack_group_table', ['stack_id', 'group_id'])
    op.create_primary_key('pk_stack_user_table', 'stack_user_table', ['stack_id', 'user_id'])


def downgrade():
    """Drop primary keys needed for BDR compatibility."""
    op.drop_constaint('pk_update_bug_table', 'update_bug_table', 'primary')
    op.drop_constaint('pk_update_cve_table', 'update_cve_table', 'primary')
    op.drop_constaint('pk_bug_cve_table', 'bug_cve_table', 'primary')
    op.drop_constaint('pk_user_package_table', 'user_package_table', 'primary')
    op.drop_constaint('pk_user_group_table', 'user_group_table', 'primary')
    op.drop_constaint('pk_stack_group_table', 'stack_group_table', 'primary')
    op.drop_constaint('pk_stack_user_table', 'stack_user_table', 'primary')
