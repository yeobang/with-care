"""P9 conduct: session cancel columns + session_incidents

Revision ID: 9c4e2f7a1b5d
Revises: 7b1d4e9f2c3a
Create Date: 2026-08-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c4e2f7a1b5d'
down_revision: Union[str, Sequence[str], None] = '7b1d4e9f2c3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("care_sessions", sa.Column("canceled_at", sa.DateTime(), nullable=True))
    op.add_column(
        "care_sessions",
        sa.Column("canceled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_table(
        "session_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("care_sessions.id"), nullable=False),
        sa.Column("crew_id", sa.String(36), sa.ForeignKey("crews.id"), nullable=False),
        sa.Column("reported_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("offender_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("fine_krw", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", "offender_id", "kind"),
    )
    op.execute("ALTER TABLE session_incidents ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("session_incidents")
    op.drop_column("care_sessions", "canceled_by")
    op.drop_column("care_sessions", "canceled_at")
