"""Add ci_status to builds

Revision ID: 4b357c65441e
Revises: b01a62d98aa4
Create Date: 2017-05-11 20:13:41.879435
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b357c65441e'
down_revision = 'b01a62d98aa4'


def upgrade():
    """ Add the ci_status to builds with the corresponding enum. """

    op.execute(
        "CREATE TYPE ck_ci_status AS ENUM "
        "('ignored', 'queued', 'running', 'passed', 'failed', 'waiting')")

    op.add_column(
        'builds',
        sa.Column(
            'ci_status',
            sa.Enum(
                'ignored', 'queued', 'running', 'passed', 'failed', 'waiting',
                name='ck_ci_status'),
            nullable=True
        )
    )


def downgrade():
    """ Remove the ci_status from builds with the corresponding enum. """
    op.drop_column('builds', 'ci_status')
    op.execute("DROP TYPE ck_ci_status")
