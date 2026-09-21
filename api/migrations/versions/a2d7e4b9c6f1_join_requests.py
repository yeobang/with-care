"""§29: 초대 다회용화 + 합류 승인 관문

Revision ID: a2d7e4b9c6f1
Revises: f1c8d2e5a9b4
Create Date: 2026-09-21

invites.used_by(1회용)를 버리고 max_uses/revoked_at으로 바꾼다.
기존에 소비된 초대는 정원이 찬 것으로 간주해 revoked_at을 채운다 — 이미 쓰인
링크가 마이그레이션으로 되살아나면 안 되기 때문이다.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2d7e4b9c6f1"
down_revision: Union[str, Sequence[str], None] = "f1c8d2e5a9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invites", sa.Column("max_uses", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("invites", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    # 이미 사용된 1회용 초대는 되살리지 않는다
    op.execute("UPDATE invites SET revoked_at = now() WHERE used_by IS NOT NULL")
    op.drop_column("invites", "used_by")

    op.create_table(
        "join_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("crew_id", sa.String(length=36), sa.ForeignKey("crews.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invite_token", sa.String(length=36), sa.ForeignKey("invites.token"), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False, server_default="parent"),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("crew_id", "user_id", name="uq_join_request_crew_user"),
    )
    op.create_index("ix_join_requests_crew_status", "join_requests", ["crew_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_join_requests_crew_status", table_name="join_requests")
    op.drop_table("join_requests")
    op.add_column("invites", sa.Column("used_by", sa.String(length=36), nullable=True))
    op.drop_column("invites", "revoked_at")
    op.drop_column("invites", "max_uses")
