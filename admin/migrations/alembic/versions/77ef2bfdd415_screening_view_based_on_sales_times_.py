"""screening view based on sales times rather than status

Revision ID: 77ef2bfdd415
Revises: eed1929381d4
Create Date: 2026-09-14 20:36:35.718919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77ef2bfdd415'
down_revision: Union[str, Sequence[str], None] = 'eed1929381d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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
    WHERE s.sale_start_time IS NOT NULL
      AND s.sale_end_time IS NOT NULL
      AND NOW() BETWEEN s.sale_start_time AND s.sale_end_time
""")


def downgrade() -> None:
    """Downgrade schema."""
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
    WHERE s.status = 'on_sale'
""")
