"""Add bug and testcase requirements.

Revision ID: 1c58aa468b17
Revises: 46f84789bec4
Create Date: 2014-10-29 14:53:13.033699

"""

# revision identifiers, used by Alembic.
revision = '1c58aa468b17'
down_revision = '46f84789bec4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('updates',
                  sa.Column('require_bugs', sa.Boolean(), nullable=True))
    op.add_column('updates',
                  sa.Column('require_testcases', sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column('updates', 'require_testcases')
    op.drop_column('updates', 'require_bugs')
