"""fix_genre_enum_casing

Revision ID: 4b3e7874b98f
Revises: d25d6671ee0d
Create Date: 2026-09-14 15:50:55.127648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b3e7874b98f'
down_revision: Union[str, Sequence[str], None] = 'd25d6671ee0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""fix genre enum casing

Revision ID: your_revision_id
Revises: your_previous_revision_id
Create Date: 2026-09-14

"""

# Define your desired capitalized genres for the final enum
# Add any missing genres (like Comedy, Drama, etc.) to this list!
CAPITALIZED_GENRES = (
    "Action", 
    "Adventure", 
    "Animation", 
    "Comedy",
    "Drama",
    "Fantasy",
    "Horror",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Thriller",
    "War",
    "Western",
    "Other"
)

# Define the old lowercase genres to support a clean rollback if needed
LOWERCASE_GENRES = (
    "action", 
    "adventure", 
    "animation",
    "comedy",
    "drama",
    "fantasy",
    "horror",
    "mystery",
    "romance",
    "sci-fi",
    "thriller",
    "war",
    "western",
    "other"
)


def upgrade() -> None:
    # 1. Temporarily change the column to a plain VARCHAR string
    op.alter_column(
        'movies',
        'genre',
        existing_type=sa.Enum(*LOWERCASE_GENRES, name='moviegenre'),
        type_=sa.String(255),
        nullable=True
    )

    # 2. Hard rewrite the lowercase text values to proper case
    op.execute("UPDATE movies SET genre = 'Other' WHERE genre = 'other'")
    # If you have other genres needing updates, add them here:
    # op.execute("UPDATE movies SET genre = 'Action' WHERE genre = 'action'")

    # 3. Re-apply the ENUM definition with capitalized parameters
    op.alter_column(
        'movies',
        'genre',
        existing_type=sa.String(255),
        type_=sa.Enum(*CAPITALIZED_GENRES, name='moviegenre'),
        nullable=True
    )


def downgrade() -> None:
    # 1. Revert back to VARCHAR to allow downgrading the casing safely
    op.alter_column(
        'movies',
        'genre',
        existing_type=sa.Enum(*CAPITALIZED_GENRES, name='moviegenre'),
        type_=sa.String(255),
        nullable=True
    )

    # 2. Revert values back to lowercase
    op.execute("UPDATE movies SET genre = 'other' WHERE genre = 'Other'")

    # 3. Restore the old lowercase ENUM constraint
    op.alter_column(
        'movies',
        'genre',
        existing_type=sa.String(255),
        type_=sa.Enum(*LOWERCASE_GENRES, name='moviegenre'),
        nullable=True
    )
