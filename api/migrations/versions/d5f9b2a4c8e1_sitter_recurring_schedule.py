"""§31 S1-2: 4주 정기 일정과 회차 연결.

Revision ID: d5f9b2a4c8e1
Revises: c4e8a1f3b7d2
"""
from alembic import op
import sqlalchemy as sa

revision = "d5f9b2a4c8e1"
down_revision = "c4e8a1f3b7d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sitter_requests", sa.Column("weekdays", sa.String(13), nullable=True))
    op.add_column("sitter_requests", sa.Column("schedule_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_sitter_schedule", "sitter_requests", "sitter_requests", ["schedule_id"], ["id"])
    op.create_unique_constraint("uq_sitter_schedule_date", "sitter_requests", ["schedule_id", "date"])


def downgrade() -> None:
    op.drop_constraint("uq_sitter_schedule_date", "sitter_requests", type_="unique")
    op.drop_constraint("fk_sitter_schedule", "sitter_requests", type_="foreignkey")
    op.drop_column("sitter_requests", "schedule_id")
    op.drop_column("sitter_requests", "weekdays")
