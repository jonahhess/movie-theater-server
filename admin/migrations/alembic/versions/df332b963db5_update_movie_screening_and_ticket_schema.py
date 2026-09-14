"""update movie screening and ticket schema

Revision ID: df332b963db5
Revises: 7c4e9f2a1b6d
Create Date: 2026-09-14 10:19:54.535368

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df332b963db5'
down_revision: Union[str, Sequence[str], None] = '7c4e9f2a1b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================
    # MOVIES
    # =========================================================

    # New nullable columns first.
    op.add_column(
        "movies",
        sa.Column(
            "tagline",
            sa.String(500),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "genre",
            sa.Enum(
                "Action",
                "Adventure",
                "Animation",
                "Comedy",
                "Crime",
                "Documentary",
                "Drama",
                "Fantasy",
                "Horror",
                "Mystery",
                "Romance",
                "Sci-Fi",
                "Thriller",
                "War",
                "Western",
                "Other",
                name="movie_genre_enum",
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "country",
            sa.Enum(
                "USA",
                "UK",
                "Canada",
                "Australia",
                "France",
                "Germany",
                "Italy",
                "Spain",
                "Japan",
                "South Korea",
                "India",
                "China",
                "Israel",
                "Other",
                name="movie_country_enum",
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "language",
            sa.Enum(
                "English",
                "Hebrew",
                "Arabic",
                "French",
                "Spanish",
                "German",
                "Italian",
                "Portuguese",
                "Russian",
                "Japanese",
                "Korean",
                "Chinese",
                "Hindi",
                "Other",
                name="movie_language_enum",
            ),
            nullable=False,
            server_default="English",
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "imdb_rating",
            sa.Numeric(3, 1),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "rotten_tomatoes_score",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "director",
            sa.String(100),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "cast",
            sa.String(255),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "trailer_url",
            sa.String(255),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "poster_url",
            sa.String(255),
            nullable=True,
        ),
    )

    op.add_column(
        "movies",
        sa.Column(
            "backdrop_url",
            sa.String(255),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # Existing movies need values for the new NOT NULL fields.
    #
    # Choose defaults appropriate for your application.
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE movies
        SET genre = 'Other'
        WHERE genre IS NULL
        """
    )

    op.execute(
        """
        UPDATE movies
        SET country = 'Other'
        WHERE country IS NULL
        """
    )

    # Now make genre/country NOT NULL.
    op.alter_column(
        "movies",
        "genre",
        existing_type=sa.Enum(
            "Action",
            "Adventure",
            "Animation",
            "Comedy",
            "Crime",
            "Documentary",
            "Drama",
            "Fantasy",
            "Horror",
            "Mystery",
            "Romance",
            "Sci-Fi",
            "Thriller",
            "War",
            "Western",
            "Other",
            name="movie_genre_enum",
        ),
        nullable=False,
    )

    op.alter_column(
        "movies",
        "country",
        existing_type=sa.Enum(
            "USA",
            "UK",
            "Canada",
            "Australia",
            "France",
            "Germany",
            "Italy",
            "Spain",
            "Japan",
            "South Korea",
            "India",
            "China",
            "Israel",
            "Other",
            name="movie_country_enum",
        ),
        nullable=False,
    )


    # =========================================================
    # AUDITORIUMS
    # =========================================================

    op.add_column(
        "auditoriums",
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "frozen",
                "inactive",
                name="auditorium_status_enum",
            ),
            nullable=False,
            server_default="active",
        ),
    )

    # Preserve existing is_active state.
    op.execute(
        """
        UPDATE auditoriums
        SET status =
            CASE
                WHEN is_active = 1 THEN 'active'
                ELSE 'inactive'
            END
        """
    )

    op.drop_column(
        "auditoriums",
        "is_active",
    )


    # =========================================================
    # SCREENINGS
    # =========================================================

    # Add nullable first so existing rows don't fail.
    op.add_column(
        "screenings",
        sa.Column(
            "end_time",
            sa.DateTime(),
            nullable=True,
        ),
    )

    # Calculate end_time from the movie duration.
    #
    # MySQL:
    # DATE_ADD(start_time, INTERVAL duration_minutes MINUTE)
    #
    op.execute(
        """
        UPDATE screenings s
        JOIN movies m ON m.id = s.movie_id
        SET s.end_time = DATE_ADD(
            s.start_time,
            INTERVAL m.duration_minutes MINUTE
        )
        WHERE s.end_time IS NULL
        """
    )

    # Now make it NOT NULL.
    op.alter_column(
        "screenings",
        "end_time",
        existing_type=sa.DateTime(),
        nullable=False,
    )

    # index=True in the model means Alembic needs an index.
    op.create_index(
        "ix_screenings_end_time",
        "screenings",
        ["end_time"],
        unique=False,
    )


    # =========================================================
    # TICKETS
    # =========================================================

    # Add the replacement columns as nullable initially.
    op.add_column(
        "tickets",
        sa.Column(
            "screening_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "tickets",
        sa.Column(
            "seat_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # ---------------------------------------------------------
    # Copy the existing relationships.
    #
    # tickets.screening_seat_id
    #              ↓
    #       screening_seats
    #          /       \
    # screening_id    seat_id
    # ---------------------------------------------------------

    op.execute(
        """
        UPDATE tickets t
        JOIN screening_seats ss
            ON ss.id = t.screening_seat_id
        SET
            t.screening_id = ss.screening_id,
            t.seat_id = ss.seat_id
        """
    )

    # Add new foreign keys.
    op.create_foreign_key(
        "fk_tickets_screening_id",
        "tickets",
        "screenings",
        ["screening_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_foreign_key(
        "fk_tickets_seat_id",
        "tickets",
        "seats",
        ["seat_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Existing tickets should now all have values.
    op.alter_column(
        "tickets",
        "screening_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "tickets",
        "seat_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.add_column(
    "tickets",
    sa.Column(
        "active_seat_id",
        sa.Integer(),
        sa.Computed(
            "CASE WHEN status = 'cancelled' THEN NULL ELSE seat_id END",
            persisted=True,
        ),
        nullable=True,
    ),
)

    op.create_unique_constraint(
        "unique_active_ticket_seat_per_screening",
        "tickets",
        ["screening_id", "active_seat_id"],
)


    # =========================================================
    # REMOVE OLD TICKET -> SCREENING_SEAT RELATIONSHIP
    # =========================================================

    # IMPORTANT:
    # This constraint name may differ in your actual database.
    #
    # Verify with:
    #
    # SHOW CREATE TABLE tickets;
    #
    op.drop_constraint(
        "tickets_ibfk_1",
        "tickets",
        type_="foreignkey",
    )

    op.drop_column(
        "tickets",
        "screening_seat_id",
    )


def downgrade() -> None:
    # =========================================================
    # TICKETS
    # =========================================================

    op.drop_constraint(
        "unique_active_ticket_seat_per_screening",
        "tickets",
        type_="unique",
    )

    op.drop_column(
        "tickets",
        "active_seat_id",
    )

    # Recreate screening_seat_id.
    #
    # It must initially be nullable because the column needs to
    # be populated before we can make it NOT NULL.
    op.add_column(
        "tickets",
        sa.Column(
            "screening_seat_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Reconstruct the old relationship.
    #
    # Every ticket's (screening_id, seat_id) pair should correspond
    # to a row in screening_seats.
    op.execute(
        """
        UPDATE tickets t
        JOIN screening_seats ss
            ON ss.screening_id = t.screening_id
            AND ss.seat_id = t.seat_id
        SET t.screening_seat_id = ss.id
        """
    )

    # Restore the old FK.
    op.create_foreign_key(
        "tickets_ibfk_1",
        "tickets",
        "screening_seats",
        ["screening_seat_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Existing tickets should now all have a screening_seat_id.
    op.alter_column(
        "tickets",
        "screening_seat_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Remove the new FKs.
    op.drop_constraint(
        "fk_tickets_screening_id",
        "tickets",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_tickets_seat_id",
        "tickets",
        type_="foreignkey",
    )

    # Remove the new ticket columns.
    op.drop_column(
        "tickets",
        "screening_id",
    )

    op.drop_column(
        "tickets",
        "seat_id",
    )


    # =========================================================
    # SCREENINGS
    # =========================================================

    op.drop_index(
        "ix_screenings_end_time",
        table_name="screenings",
    )

    op.drop_column(
        "screenings",
        "end_time",
    )


    # =========================================================
    # AUDITORIUMS
    # =========================================================

    # Recreate is_active.
    op.add_column(
        "auditoriums",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )

    # Convert the new status back into the old boolean.
    op.execute(
        """
        UPDATE auditoriums
        SET is_active =
            CASE
                WHEN status = 'active' THEN 1
                ELSE 0
            END
        """
    )

    op.drop_column(
        "auditoriums",
        "status",
    )


    # =========================================================
    # MOVIES
    # =========================================================

    op.drop_column(
        "movies",
        "backdrop_url",
    )

    op.drop_column(
        "movies",
        "poster_url",
    )

    op.drop_column(
        "movies",
        "trailer_url",
    )

    op.drop_column(
        "movies",
        "cast",
    )

    op.drop_column(
        "movies",
        "director",
    )

    op.drop_column(
        "movies",
        "rotten_tomatoes_score",
    )

    op.drop_column(
        "movies",
        "imdb_rating",
    )

    op.drop_column(
        "movies",
        "language",
    )

    op.drop_column(
        "movies",
        "country",
    )

    op.drop_column(
        "movies",
        "genre",
    )

    op.drop_column(
        "movies",
        "tagline",
    )
