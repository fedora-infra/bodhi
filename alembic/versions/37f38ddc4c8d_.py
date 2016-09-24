"""Do not allow NULL values in the text column of the comments table.

Revision ID: 37f38ddc4c8d
Revises: 3c72757fa59e
Create Date: 2016-09-21 19:51:04.946521

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '37f38ddc4c8d'
down_revision = '3c72757fa59e'


def upgrade():
    """
    We will need to set all existing NULL comments to "", then change the column to disallow NULL comments.
    """
    # Build a fake mini version of the comments table so we can form an UPDATE statement.
    comments = sa.sql.table('comments', sa.sql.column('text', sa.UnicodeText))
    # Set existing NULL comments to "".
    op.execute(comments.update().where(comments.c.text==None).values({'text': op.inline_literal('')}))

    # Disallow new NULL comments.
    op.alter_column('comments', 'text', existing_type=sa.TEXT(), nullable=False)


def downgrade():
    op.alter_column('comments', 'text', existing_type=sa.TEXT(), nullable=True)
