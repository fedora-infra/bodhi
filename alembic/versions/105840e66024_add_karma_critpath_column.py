"""Add karma_critpath column.

Revision ID: 105840e66024
Revises: 5834b7b7e4cb
Create Date: 2014-05-08 10:00:21.609055

"""

# revision identifiers, used by Alembic.
revision = '105840e66024'
down_revision = '5834b7b7e4cb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('comments', sa.Column('karma_critpath', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('comments', 'karma_critpath')
