"""create_views

Revision ID: 3d4b49a7d0c4
Revises: 430c8a0ac502
Create Date: 2026-08-30 22:45:48.528800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d4b49a7d0c4'
down_revision: Union[str, Sequence[str], None] = '430c8a0ac502'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
     # --- View 1: Movies Public View ---
    op.execute("""
        CREATE OR REPLACE VIEW movies_public_view AS
        SELECT id, title, description, duration_minutes, rating, release_date
        FROM movies 
        WHERE status = 'now_showing'
    """)

    # --- View 2: Order Summaries ---
    op.execute("""
        CREATE OR REPLACE VIEW auditoriums_public_view AS
        SELECT a.id, a.name,
        COALESCE(
            MAX(s.is_accessible), 
            0
        ) AS is_accessible
        FROM auditoriums a
        LEFT JOIN seats s ON a.id = s.auditorium_id
        GROUP BY a.id, a.name
    """)

    # --- View 3: Combined Analytics ---
    # (Note: This depends on View 1 and View 2, so it is placed last)
    op.execute("""
        CREATE OR REPLACE VIEW screenings_public_view AS
        SELECT s.id, s.movie_id, s.auditorium_id, s.start_time, s.price
        FROM screenings s
        WHERE s.status = 'on_sale'
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # --- Drop views in reverse order of creation ---
    op.execute("DROP VIEW IF EXISTS screenings_public_view")
    op.execute("DROP VIEW IF EXISTS auditoriums_public_view")
    op.execute("DROP VIEW IF EXISTS movies_public_view")
