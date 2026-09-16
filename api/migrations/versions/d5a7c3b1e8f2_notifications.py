"""notifications inbox

Revision ID: d5a7c3b1e8f2
Revises: b8f3d6c2e9a1
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5a7c3b1e8f2'
down_revision: Union[str, Sequence[str], None] = 'b8f3d6c2e9a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("crew_id", sa.String(36), sa.ForeignKey("crews.id"), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.String(400), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
