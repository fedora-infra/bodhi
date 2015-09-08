"""Add buildroot overrides

Revision ID: 6a438fe37fd
Revises: 3b85a0db1a5d
Create Date: 2014-06-04 18:26:39.899842

"""

# revision identifiers, used by Alembic.
revision = '6a438fe37fd'
down_revision = '3b85a0db1a5d'

from datetime import datetime

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('buildroot_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('build_id', sa.Integer(), nullable=False),
        sa.Column('submitter_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Unicode(), nullable=False),
        sa.Column('submission_date', sa.DateTime(), default=datetime.utcnow,
                  nullable=False),
        sa.Column('expiration_date', sa.DateTime(), nullable=False),
        sa.Column('expired_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
        sa.ForeignKeyConstraint(['submitter_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('buildroot_overrides')
