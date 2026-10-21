"""Index build_testcase_table build_id.

Revision ID: bcd25547c613
Revises: 16864f8ff395
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "bcd25547c613"
down_revision = "16864f8ff395"


def upgrade():
    """Add an index on build_testcase_table.build_id."""
    op.create_index(
        op.f("ix_build_testcase_table_build_id"),
        "build_testcase_table",
        ["build_id"],
        unique=False,
    )


def downgrade():
    """Drop the index on build_testcase_table.build_id."""
    op.drop_index(
        op.f("ix_build_testcase_table_build_id"),
        table_name="build_testcase_table",
    )
