"""P10 sitter track: roles, sitter profiles/requests/quotes, session source split

Revision ID: b8f3d6c2e9a1
Revises: 9c4e2f7a1b5d
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8f3d6c2e9a1'
down_revision: Union[str, Sequence[str], None] = '9c4e2f7a1b5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # §25-1: 시터 역할
    op.add_column("crew_members", sa.Column("role", sa.String(10), nullable=False, server_default="parent"))
    op.add_column("invites", sa.Column("role", sa.String(10), nullable=False, server_default="parent"))

    op.create_table(
        "sitter_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("hourly_krw", sa.Integer(), nullable=False),
        sa.Column("intro", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sitter_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("crew_id", sa.String(36), sa.ForeignKey("crews.id"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("start_hour", sa.Integer(), nullable=False),
        sa.Column("end_hour", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sitter_request_children",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("sitter_requests.id"), nullable=False),
        sa.Column("child_id", sa.String(36), sa.ForeignKey("children.id"), nullable=False),
        sa.UniqueConstraint("request_id", "child_id"),
    )
    op.create_table(
        "sitter_quotes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("sitter_requests.id"), nullable=False),
        sa.Column("sitter_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("hourly_krw", sa.Integer(), nullable=False),
        sa.Column("surge", sa.Boolean(), nullable=False),
        sa.Column("total_krw", sa.Integer(), nullable=False),
        sa.Column("per_family_krw", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_id", "sitter_user_id"),
    )
    op.create_table(
        "sitter_quote_families",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("sitter_quotes.id"), nullable=False),
        sa.Column("guardian_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("quote_id", "guardian_id"),
    )
    for t in ("sitter_profiles", "sitter_requests", "sitter_request_children", "sitter_quotes", "sitter_quote_families"):
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")

    # 세션 출처 이원화 (§25-4): assignment 또는 sitter_quote
    op.alter_column("care_sessions", "assignment_id", existing_type=sa.String(36), nullable=True)
    op.add_column(
        "care_sessions",
        sa.Column("sitter_quote_id", sa.String(36), sa.ForeignKey("sitter_quotes.id"), nullable=True, unique=True),
    )


def downgrade() -> None:
    op.drop_column("care_sessions", "sitter_quote_id")
    op.alter_column("care_sessions", "assignment_id", existing_type=sa.String(36), nullable=False)
    for t in ("sitter_quote_families", "sitter_quotes", "sitter_request_children", "sitter_requests", "sitter_profiles"):
        op.drop_table(t)
    op.drop_column("invites", "role")
    op.drop_column("crew_members", "role")
