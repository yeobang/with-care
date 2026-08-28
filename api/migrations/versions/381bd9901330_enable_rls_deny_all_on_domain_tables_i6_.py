"""enable RLS deny-all on domain tables (I6 defense-in-depth)

Revision ID: 381bd9901330
Revises: 8cf7cacb91df
Create Date: 2026-08-28 15:08:48.300131

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '381bd9901330'
down_revision: Union[str, Sequence[str], None] = '8cf7cacb91df'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
