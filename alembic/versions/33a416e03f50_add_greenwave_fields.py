"""Add the fields for caching the Greenwave decision for each update.

Revision ID: 33a416e03f50
Revises: 2a10629168e4
Create Date: 2017-07-06 13:52:50.892504
"""
from alembic import op
from sqlalchemy import Column, Enum, Unicode


# revision identifiers, used by Alembic.
revision = '33a416e03f50'
down_revision = '2a10629168e4'


def upgrade():
    op.execute(
        "CREATE TYPE ck_test_gating_status AS ENUM "
        "('ignored', 'queued', 'running', 'passed', 'failed', 'waiting')")
    op.add_column(
        'updates',
        Column(
            'test_gating_status',
            Enum(
                'ignored', 'queued', 'running', 'passed', 'failed', 'waiting',
                name='ck_test_gating_status'),
            nullable=True
        )
    )
    op.add_column('updates', Column('greenwave_summary_string', Unicode(255)))


def downgrade():
    op.drop_column('updates', 'test_gating_status')
    op.execute("DROP TYPE ck_test_gating_status")
    op.drop_column('updates', 'greenwave_summary_string')
