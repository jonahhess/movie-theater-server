"""add sales times to screenings

Revision ID: eed1929381d4
Revises: 4b3e7874b98f
Create Date: 2026-09-14 18:39:39.703033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eed1929381d4'
down_revision: Union[str, Sequence[str], None] = '4b3e7874b98f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('screenings', sa.Column('sale_start_time', sa.DateTime(), nullable=True))
    op.add_column('screenings', sa.Column('sale_end_time', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('screenings', 'sale_start_time')
    op.drop_column('screenings', 'sale_end_time')
