"""community: posts, comments, likes + user town (§27)

Revision ID: e9b2f4a7c1d3
Revises: d5a7c3b1e8f2
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e9b2f4a7c1d3'
down_revision: Union[str, Sequence[str], None] = 'd5a7c3b1e8f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("town_code", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("town_name", sa.String(50), nullable=True))

    op.create_table(
        "posts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("crew_id", sa.String(36), sa.ForeignKey("crews.id"), nullable=True),
        sa.Column("town_code", sa.String(20), nullable=True),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("category", sa.String(10), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_posts_town_created", "posts", ["town_code", "created_at"])
    op.create_index("ix_posts_crew_created", "posts", ["crew_id", "created_at"])

    op.create_table(
        "comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_comments_post", "comments", ["post_id", "created_at"])

    op.create_table(
        "post_likes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("post_id", "user_id"),
    )
    for t in ("posts", "comments", "post_likes"):
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("post_likes")
    op.drop_index("ix_comments_post", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_posts_crew_created", table_name="posts")
    op.drop_index("ix_posts_town_created", table_name="posts")
    op.drop_table("posts")
    op.drop_column("users", "town_name")
    op.drop_column("users", "town_code")
