"""Add some stock stuff

Revision ID: afc57bd04606
Revises: 580385482580
Create Date: 2017-02-25 18:59:11.096406

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'afc57bd04606'
down_revision = '580385482580'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('guild', sa.Column('stock_announcement_id', sa.BigInteger(), nullable=True))
    op.create_unique_constraint(None, 'stock', ['channel_id'])
    # op.add_column('user__stock', sa.Column('crashed', sa.Boolean(), nullable=False))
    # op.add_column('user__stock', sa.Column('crashed_at', sa.Float(), nullable=False))
    conn = op.get_bind()
    conn.execute("""BEGIN;
ALTER TABLE user__stock ADD COLUMN crashed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE user__stock ADD COLUMN crashed_at FLOAT NOT NULL DEFAULT 0.0;
COMMIT;
""")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user__stock', 'crashed_at')
    op.drop_column('user__stock', 'crashed')
    op.drop_constraint(None, 'stock', type_='unique')
    op.drop_column('guild', 'stock_announcement_id')
    # ### end Alembic commands ###
