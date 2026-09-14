"""add purchaser uuid to tickets

Revision ID: 8a7d4c2f5b91
Revises: 2f922b66985c
Create Date: 2026-09-04 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8a7d4c2f5b91"
down_revision: str | Sequence[str] | None = "2f922b66985c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tickets",
        sa.Column("purchaser_uuid", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_tickets_purchaser_uuid"),
        "tickets",
        ["purchaser_uuid"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_tickets_purchaser_uuid"), table_name="tickets")
    op.drop_column("tickets", "purchaser_uuid")
