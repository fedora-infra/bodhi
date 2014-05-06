"""New karma tables

Revision ID: 5834b7b7e4cb
Revises: 7f3bd827e70
Create Date: 2014-05-06 15:42:08.805202

"""

# revision identifiers, used by Alembic.
revision = '5834b7b7e4cb'
down_revision = '7f3bd827e70'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'comment_testcase_assoc',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('karma', sa.Integer(), nullable=True),
        sa.Column('comment_id', sa.Integer(), nullable=True),
        sa.Column('testcase_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ),
        sa.ForeignKeyConstraint(['testcase_id'], ['testcases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'comment_bug_assoc',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('karma', sa.Integer(), nullable=True),
        sa.Column('comment_id', sa.Integer(), nullable=True),
        sa.Column('bug_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['bug_id'], ['bugs.id'], ),
        sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('comment_bug_assoc')
    op.drop_table('comment_testcase_assoc')
