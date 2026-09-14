"""adding checkout id to tickets

Revision ID: 2f922b66985c
Revises: 3d4b49a7d0c4
Create Date: 2026-08-31 18:05:59.882154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f922b66985c'
down_revision: Union[str, Sequence[str], None] = '3d4b49a7d0c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # tickets table add column checkout_id
    op.add_column('tickets', sa.Column('checkout_id', sa.String(length=36), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # tickets table drop column checkout_id
    op.drop_column('tickets', 'checkout_id')
