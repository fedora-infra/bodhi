"""Add update.date_testing/stable timestamps

Revision ID: 13cfca635b99
Revises: 52dcf7261a86
Create Date: 2015-09-02 15:55:40.940168

"""

# revision identifiers, used by Alembic.
revision = '13cfca635b99'
down_revision = '52dcf7261a86'

from alembic import op
import sqlalchemy as sa

from bodhi.models import Update


def upgrade():
    op.add_column('updates', sa.Column('date_stable', sa.DateTime(), nullable=True))
    op.add_column('updates', sa.Column('date_testing', sa.DateTime(), nullable=True))

    engine = op.get_bind().engine
    session = sa.orm.scoped_session(sa.orm.sessionmaker(bind=engine))

    for update in session.query(Update).all():
        for comment in update.comments:
            if comment.user.name == u'bodhi':
                if comment.text == u'This update has been pushed to testing':
                    update.date_testing = comment.timestamp
                    print('Setting date_testing for %s' % update.title)
                elif comment.text == u'This update has been pushed to stable':
                    update.date_stable = comment.timestamp
                    print('Setting date_stable for %s' % update.title)

    session.commit()


def downgrade():
    op.drop_column('updates', 'date_testing')
    op.drop_column('updates', 'date_stable')
