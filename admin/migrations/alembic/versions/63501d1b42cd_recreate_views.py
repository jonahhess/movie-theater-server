"""recreate views

Revision ID: 63501d1b42cd
Revises: 1ce4c865da1d
Create Date: 2026-09-15 17:21:43.980911

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63501d1b42cd'
down_revision: Union[str, Sequence[str], None] = '1ce4c865da1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- View 1: Movies Public View ---
    op.execute("""
        CREATE OR REPLACE VIEW movies_public_view AS
        SELECT
            id,
            title,
            description,
            duration_minutes,
            rating,
            release_date,
            tagline,
            genre,
            country,
            language,
            imdb_rating,
            rotten_tomatoes_score,
            director,
            `cast`,
            trailer_url,
            poster_url,
            backdrop_url
        FROM movies
        WHERE status = 'now_showing'
    """)

    # --- View 2: Auditoriums Public View ---
    op.execute("""
        CREATE OR REPLACE VIEW auditoriums_public_view AS
        SELECT
            a.id,
            a.name,
            COALESCE(
                MAX(s.is_accessible),
                0
            ) AS is_accessible
        FROM auditoriums a
        LEFT JOIN seats s
            ON a.id = s.auditorium_id
        GROUP BY a.id, a.name
    """)
    
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
    # Drop the views in reverse order of creation
    op.execute("DROP VIEW IF EXISTS screenings_public_view")
    op.execute("DROP VIEW IF EXISTS auditoriums_public_view")
    op.execute("DROP VIEW IF EXISTS movies_public_view")
