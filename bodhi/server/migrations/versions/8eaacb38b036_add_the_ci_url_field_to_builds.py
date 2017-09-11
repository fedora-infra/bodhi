"""Add the ci_url field to builds

Revision ID: 8eaacb38b036
Revises: 4b357c65441e
Create Date: 2017-05-18 12:01:20.698762
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8eaacb38b036'
down_revision = '4b357c65441e'


def upgrade():
    """ Add the ci_url to builds. """

    op.add_column(
        'builds',
        sa.Column('ci_url', sa.UnicodeText, nullable=True)
    )


def downgrade():
    """ Remove the ci_url from builds. """
    op.drop_column('builds', 'ci_url')
