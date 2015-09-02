"""Add a User.email column

Revision ID: 52dcf7261a86
Revises: 479aaacfc5c7
Create Date: 2015-09-02 12:37:10.516974

"""

# revision identifiers, used by Alembic.
revision = '52dcf7261a86'
down_revision = '479aaacfc5c7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('users', sa.Column('email', sa.VARCHAR(),
                                     nullable=True))


def downgrade():
    op.drop_column('users', 'email')
