"""chat: rooms, members, messages (§28)

Revision ID: f1c8d2e5a9b4
Revises: e9b2f4a7c1d3
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f1c8d2e5a9b4'
down_revision: Union[str, Sequence[str], None] = 'e9b2f4a7c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_rooms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("crew_id", sa.String(36), sa.ForeignKey("crews.id"), nullable=False),
        sa.Column("context_kind", sa.String(20), nullable=True),
        sa.Column("context_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_rooms_crew", "chat_rooms", ["crew_id", "kind"])
    op.create_index("ix_rooms_context", "chat_rooms", ["context_kind", "context_id"])
    op.create_table(
        "chat_members",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("chat_rooms.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_read_at", sa.DateTime(), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("room_id", "user_id"),
    )
    op.create_index("ix_chat_members_user", "chat_members", ["user_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("chat_rooms.id"), nullable=False),
        sa.Column("sender_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_messages_room_created", "chat_messages", ["room_id", "created_at"])
    for t in ("chat_rooms", "chat_members", "chat_messages"):
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_members")
    op.drop_table("chat_rooms")
