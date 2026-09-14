"""replace status with is_cancelled

Revision ID: 1ce4c865da1d
Revises: dcfb1a06d459
Create Date: 2026-09-14 20:49:06.830599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ce4c865da1d'
down_revision: Union[str, Sequence[str], None] = 'dcfb1a06d459'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('screenings', sa.Column('is_cancelled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.drop_column('screenings', 'status')

    op.execute("""
    CREATE OR REPLACE VIEW screenings_public_view AS
    SELECT
        s.id,
        s.movie_id,
        s.auditorium_id,
        s.start_time,
        s.end_time,
        s.price
    FROM screenings s
    WHERE s.is_cancelled = FALSE
      AND s.sale_start_time IS NOT NULL
      AND s.sale_end_time IS NOT NULL
      AND NOW() BETWEEN s.sale_start_time AND s.sale_end_time
""")



def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('screenings', sa.Column('status', sa.String(), nullable=False, server_default='active'))
    op.drop_column('screenings', 'is_cancelled')
    
    op.execute("""
    CREATE OR REPLACE VIEW screenings_public_view AS
    SELECT
        s.id,
        s.movie_id,
        s.auditorium_id,
        s.start_time,
        s.end_time,
        s.price
    FROM screenings s
    WHERE s.status <> 'cancelled'
      AND s.sale_start_time IS NOT NULL
      AND s.sale_end_time IS NOT NULL
      AND NOW() BETWEEN s.sale_start_time AND s.sale_end_time
""")
