"""§31 S1: 함께 볼 때 시급 + 아이 수 비례 분할

Revision ID: c4e8a1f3b7d2
Revises: a2d7e4b9c6f1
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e8a1f3b7d2'
down_revision: Union[str, Sequence[str], None] = 'a2d7e4b9c6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sitter_profiles", sa.Column("shared_hourly_krw", sa.Integer(), nullable=True))
    op.add_column(
        "sitter_quote_families",
        sa.Column("child_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "sitter_quote_families",
        sa.Column("amount_krw", sa.Integer(), nullable=False, server_default="0"),
    )
    # 기존 견적: 그때 규칙(가정 균등)으로 계산된 금액을 가정별 금액으로 옮긴다 — 금액이 바뀌지 않는다
    op.execute(
        "UPDATE sitter_quote_families SET amount_krw = "
        "(SELECT per_family_krw FROM sitter_quotes WHERE sitter_quotes.id = sitter_quote_families.quote_id)"
    )
    op.execute(
        "UPDATE sitter_quote_families SET child_count = ("
        " SELECT COUNT(*) FROM sitter_request_children src"
        " JOIN children c ON c.id = src.child_id"
        " JOIN sitter_quotes q ON q.request_id = src.request_id"
        " WHERE q.id = sitter_quote_families.quote_id AND c.guardian_id = sitter_quote_families.guardian_id)"
    )
    op.alter_column("sitter_quotes", "per_family_krw", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute(
        "UPDATE sitter_quotes SET per_family_krw = 0 WHERE per_family_krw IS NULL"
    )
    op.alter_column("sitter_quotes", "per_family_krw", existing_type=sa.Integer(), nullable=False)
    op.drop_column("sitter_quote_families", "amount_krw")
    op.drop_column("sitter_quote_families", "child_count")
    op.drop_column("sitter_profiles", "shared_hourly_krw")
