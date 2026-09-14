"""add password hash to users

Revision ID: 7c4e9f2a1b6d
Revises: 2f922b66985c
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c4e9f2a1b6d"
down_revision: Union[str, Sequence[str], None] = "8a7d4c2f5b91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")