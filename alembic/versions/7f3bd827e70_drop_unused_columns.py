"""Drop unused columns

Revision ID: 7f3bd827e70
Revises: 18cad09c8ab6
Create Date: 2014-05-06 15:40:32.925576

"""

# revision identifiers, used by Alembic.
revision = '7f3bd827e70'
down_revision = '18cad09c8ab6'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column(u'updates', 'qa_approval_date')
    op.drop_column(u'updates', 'security_approval_date')
    op.drop_column(u'updates', 'qa_approved')
    op.drop_column(u'updates', 'security_approved')
    op.drop_column(u'updates', 'releng_approval_date')
    op.drop_column(u'updates', 'releng_approved')


def downgrade():
    op.add_column(u'updates', sa.Column('releng_approved', sa.BOOLEAN(), nullable=True))
    op.add_column(u'updates', sa.Column('releng_approval_date', sa.DATETIME(), nullable=True))
    op.add_column(u'updates', sa.Column('security_approved', sa.BOOLEAN(), nullable=True))
    op.add_column(u'updates', sa.Column('qa_approved', sa.BOOLEAN(), nullable=True))
    op.add_column(u'updates', sa.Column('security_approval_date', sa.DATETIME(), nullable=True))
    op.add_column(u'updates', sa.Column('qa_approval_date', sa.DATETIME(), nullable=True))
