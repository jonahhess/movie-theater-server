"""update views

Revision ID: d25d6671ee0d
Revises: df332b963db5
Create Date: 2026-09-14 12:14:56.086197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd25d6671ee0d'
down_revision: Union[str, Sequence[str], None] = 'df332b963db5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update public views to expose the newly added columns."""

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

    # --- View 3: Screenings Public View ---
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


def downgrade() -> None:
    """Restore the previous public view definitions."""

    op.execute("""
        CREATE OR REPLACE VIEW movies_public_view AS
        SELECT
            id,
            title,
            description,
            duration_minutes,
            rating,
            release_date
        FROM movies
        WHERE status = 'now_showing'
    """)

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
            s.price
        FROM screenings s
        WHERE s.status = 'on_sale'
    """)

