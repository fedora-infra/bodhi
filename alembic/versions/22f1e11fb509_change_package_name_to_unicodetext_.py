"""Change Package.name to UnicodeText instead of Unicode(50)

Revision ID: 22f1e11fb509
Revises: 1c58aa468b17
Create Date: 2015-07-06 15:39:13.768827

"""

# revision identifiers, used by Alembic.
revision = '22f1e11fb509'
down_revision = '1c58aa468b17'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import UnicodeText, Unicode


def upgrade():
    op.alter_column(table_name='packages', column_name='name', type_=UnicodeText)


def downgrade():
    op.alter_column(table_name='packages', column_name='name', type_=Unicode(50))
