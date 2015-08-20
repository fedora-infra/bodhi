"""Non-nullable fields for the Release.

Revision ID: 479aaacfc5c7
Revises: 22f1e11fb509
Create Date: 2015-08-19 19:46:40.785149

"""

# revision identifiers, used by Alembic.
revision = '479aaacfc5c7'
down_revision = '22f1e11fb509'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column("releases", "version", nullable=False)
    op.alter_column("releases", "branch", nullable=False)


def downgrade():
    op.alter_column("releases", "version", nullable=True)
    op.alter_column("releases", "branch", nullable=True)
