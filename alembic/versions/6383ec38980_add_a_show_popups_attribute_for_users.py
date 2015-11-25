"""Add a show_popups attribute for users.

Revision ID: 6383ec38980
Revises: 2defe1107259
Create Date: 2015-10-27 13:33:34.193337

"""

# revision identifiers, used by Alembic.
revision = '6383ec38980'
down_revision = '2defe1107259'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


def upgrade():
    op.add_column('users', sa.Column(
        'show_popups', sa.Boolean(), server_default=text('TRUE')))


def downgrade():
    op.drop_column('users', 'show_popups')
