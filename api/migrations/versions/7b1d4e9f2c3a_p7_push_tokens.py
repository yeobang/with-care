"""P7 push tokens

Revision ID: 7b1d4e9f2c3a
Revises: 3f2a9c1d5e7b
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b1d4e9f2c3a'
down_revision: Union[str, Sequence[str], None] = '3f2a9c1d5e7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token", sa.String(200), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute("ALTER TABLE push_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("push_tokens")
