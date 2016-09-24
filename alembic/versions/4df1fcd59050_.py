"""Add the new pending_signing_tag column to the releases table.

Revision ID: 4df1fcd59050
Revises: 5110dfc1a01a
Create Date: 2016-09-16 18:51:19.514301

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4df1fcd59050'
down_revision = '5110dfc1a01a'


def upgrade():
    op.add_column('releases',
                  sa.Column('pending_signing_tag', sa.UnicodeText(), server_default='',
                            nullable=False))
    # We only used the server_default to stop the new column from being NULL. Let's now drop the
    # server default.
    op.alter_column('releases', 'pending_signing_tag', server_default=None)


def downgrade():
    op.drop_column('releases', 'pending_signing_tag')
