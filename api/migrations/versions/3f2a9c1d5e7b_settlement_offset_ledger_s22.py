"""settlement offset ledger (§22): ledger_entries.settlement_id + session_id nullable, settlements.amount_credits

Revision ID: 3f2a9c1d5e7b
Revises: 876d990320ad
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f2a9c1d5e7b'
down_revision: Union[str, Sequence[str], None] = '876d990320ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # §22: 장부 항목의 출처는 세션 또는 정산 확정 둘 중 하나
    op.alter_column("ledger_entries", "session_id", existing_type=sa.String(36), nullable=True)
    op.add_column(
        "ledger_entries",
        sa.Column("settlement_id", sa.String(36), sa.ForeignKey("settlements.id"), nullable=True),
    )
    # §22-2: 상쇄는 제안 시점의 크레딧 수치로
    op.add_column(
        "settlements",
        sa.Column("amount_credits", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("settlements", "amount_credits")
    op.drop_column("ledger_entries", "settlement_id")
    op.alter_column("ledger_entries", "session_id", existing_type=sa.String(36), nullable=False)
