"""Drop the Update.karma column.

Revision ID: 06aa0e8aa5d2
Revises: 3cde3882442a
Create Date: 2016-10-26 16:55:54.875994

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '06aa0e8aa5d2'
down_revision = None


def upgrade():
    """
    Drop the karma column from the updates table.
    """
    op.drop_column('updates', 'karma')


def downgrade():
    """
    Downgrade is not supported. If we ever do want to do this for some reason, we can use the
    code from the bodhi.server.models.Update.karma() property that was written in the same
    commit that introduced this migration as a guide for how to calculate the karma column. As it is
    highly unlikely that will ever be needed, this function simply raises an Exception for now.
    """
    raise NotImplemented('Downgrade not supported')
