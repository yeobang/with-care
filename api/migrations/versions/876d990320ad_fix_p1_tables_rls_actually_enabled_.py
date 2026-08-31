"""fix: P1 tables RLS actually enabled (381bd was empty)

Revision ID: 876d990320ad
Revises: c136a836475b
Create Date: 2026-08-31 09:33:41.155799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '876d990320ad'
down_revision: Union[str, Sequence[str], None] = 'c136a836475b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 381bd9901330이 빈 껍데기였던 것의 수정 — 문자열 치환 실패로 RLS 구문 유실
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crews ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crew_members ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invites ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE charters ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE children ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE consents ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crews DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE crew_members DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invites DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE charters DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE children DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE consents DISABLE ROW LEVEL SECURITY")
