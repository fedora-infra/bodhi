"""Set NULL autokarma to True for Updates that have non-NULL stable karma thresholds.

Revision ID: 5110dfc1a01a
Revises: 37f38ddc4c8d
Create Date: 2016-09-24 02:53:42.025785

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5110dfc1a01a'
down_revision = '37f38ddc4c8d'


def upgrade():
    """Set NULL autokarma to True for Updates that have non-NULL stable karma thresholds."""
    # Build a fake mini version of the updates table so we can form an UPDATE statement.
    updates = sa.sql.table('updates', sa.sql.column('autokarma', sa.Boolean),
                           sa.sql.column('stable_karma', sa.Integer))
    # Set autokarma to True if there is a stable threshold set and autokarma is None.
    op.execute(
        updates.update().where(
            updates.c.stable_karma != None).where(updates.c.autokarma == None).values(
                {'autokarma': True}))


def downgrade():
    """There isn't a way to downgrade this migration."""
    pass
