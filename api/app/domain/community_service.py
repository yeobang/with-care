"""커뮤니티 (§27): 모임 이야기판(crew) + 동네 게시판(town).

§27의 경계 — 이 모듈이 지키는 것:
- crew 글은 멤버만 읽고 쓴다 (I6 그대로)
- town 글은 크루·아이·장부를 참조하지 않는다 (모델에 참조 자체가 없음) + 텍스트 전용
- town 글 작성은 본인인증 계정만 (스팸·익명 악용 차단). 읽기는 멤버십 무관
- 익명이어도 author_id는 남긴다 (신고·분쟁 대비). 가리는 것은 응답 계층의 일
- 삭제는 무효화 (deleted_at) — 감사 추적 원칙
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.domain import errors
from app.domain.crew_service import _require_member
from app.domain.models import (
    Comment,
    Post,
    PostCategory,
    PostLike,
    PostScope,
    User,
    _now,
)

MAX_FEED = 50


def _require_verified(user: User) -> None:
    if not user.identity_verified:
        raise errors.HandoffGateViolation("본인인증 후에 글을 쓸 수 있어요 (I1)")


def _require_town(user: User) -> str:
    if not user.town_code:
        raise ValueError("먼저 동네를 설정해주세요")
    return user.town_code


def create_post(
    db: DbSession, author: User, *, scope: PostScope, category: PostCategory,
    title: str, body: str, crew_id: str | None = None, anonymous: bool = False,
) -> Post:
    if not title.strip() or not body.strip():
        raise ValueError("제목과 내용을 채워주세요")

    if scope == PostScope.CREW:
        if not crew_id:
            raise ValueError("모임이 지정되지 않았어요")
        _require_member(db, crew_id, author.id)  # I6
        town_code = None
        anonymous = False  # 아는 사이끼리는 익명이 의미 없고, 책임 소재가 흐려진다
    else:
        _require_verified(author)  # §27: 공개 글은 본인인증 계정만
        town_code = _require_town(author)
        crew_id = None
        if category == PostCategory.NOTICE:
            raise ValueError("공지는 모임 안에서만 쓸 수 있어요")

    post = Post(
        scope=scope, crew_id=crew_id, town_code=town_code, author_id=author.id,
        anonymous=anonymous, category=category, title=title.strip()[:120], body=body.strip()[:4000],
    )
    db.add(post)
    db.flush()
    return post


def town_feed(db: DbSession, user: User, *, category: str | None = None, limit: int = 20) -> list[Post]:
    """동네 피드 — 내 동네 글만. 페이지 상한을 둬 전량 조회하지 않는다."""
    town = _require_town(user)
    q = select(Post).where(
        Post.scope == PostScope.TOWN, Post.town_code == town, Post.deleted_at.is_(None)
    )
    if category:
        q = q.where(Post.category == category)
    return list(db.scalars(q.order_by(Post.created_at.desc()).limit(min(max(limit, 1), MAX_FEED))).all())


def crew_feed(db: DbSession, crew_id: str, user: User, limit: int = 20) -> list[Post]:
    _require_member(db, crew_id, user.id)  # I6
    return list(
        db.scalars(
            select(Post)
            .where(Post.scope == PostScope.CREW, Post.crew_id == crew_id, Post.deleted_at.is_(None))
            .order_by(Post.created_at.desc())
            .limit(min(max(limit, 1), MAX_FEED))
        ).all()
    )


def get_post(db: DbSession, post_id: str, user: User) -> Post:
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise ValueError("없는 글이에요")
    if post.scope == PostScope.CREW:
        _require_member(db, post.crew_id, user.id)  # I6
    elif post.town_code != user.town_code:
        # 다른 동네 글은 보이지 않는다 (동네 경계)
        raise errors.CrewIsolationViolation("다른 동네의 글은 볼 수 없어요")
    return post


def add_comment(db: DbSession, post_id: str, author: User, body: str, anonymous: bool = False) -> Comment:
    post = get_post(db, post_id, author)  # 읽기 권한이 곧 댓글 권한
    if not body.strip():
        raise ValueError("내용을 입력해주세요")
    if post.scope == PostScope.TOWN:
        _require_verified(author)
    else:
        anonymous = False
    comment = Comment(post_id=post.id, author_id=author.id, anonymous=anonymous, body=body.strip()[:1000])
    db.add(comment)
    db.flush()
    return comment


def comments_of(db: DbSession, post_id: str, user: User) -> list[Comment]:
    get_post(db, post_id, user)
    return list(
        db.scalars(
            select(Comment)
            .where(Comment.post_id == post_id, Comment.deleted_at.is_(None))
            .order_by(Comment.created_at)
        ).all()
    )


def toggle_like(db: DbSession, post_id: str, user: User) -> tuple[int, bool]:
    """(좋아요 수, 내가 눌렀는지). 같은 사람이 두 번 눌러도 중복되지 않는다."""
    get_post(db, post_id, user)
    existing = db.scalar(select(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user.id))
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(PostLike(post_id=post_id, user_id=user.id))
        liked = True
    db.flush()
    count = db.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id)) or 0
    return int(count), liked


def delete_post(db: DbSession, post_id: str, user: User) -> None:
    """작성자만. 삭제는 무효화 — 댓글 맥락과 감사 추적을 남긴다."""
    post = db.get(Post, post_id)
    if post is None or post.deleted_at is not None:
        raise ValueError("없는 글이에요")
    if post.author_id != user.id:
        raise errors.HumanChoiceViolation("자기 글만 지울 수 있어요")
    post.deleted_at = _now()
    db.flush()


def stats(db: DbSession, post_ids: list[str], user: User) -> dict[str, dict]:
    """목록용 집계 — N+1을 피해 한 번에 센다."""
    if not post_ids:
        return {}
    likes = db.execute(
        select(PostLike.post_id, func.count()).where(PostLike.post_id.in_(post_ids)).group_by(PostLike.post_id)
    ).all()
    mine = db.scalars(
        select(PostLike.post_id).where(PostLike.post_id.in_(post_ids), PostLike.user_id == user.id)
    ).all()
    counts = db.execute(
        select(Comment.post_id, func.count())
        .where(Comment.post_id.in_(post_ids), Comment.deleted_at.is_(None))
        .group_by(Comment.post_id)
    ).all()
    lk = {pid: int(c) for pid, c in likes}
    cm = {pid: int(c) for pid, c in counts}
    return {
        pid: {"likes": lk.get(pid, 0), "comments": cm.get(pid, 0), "liked": pid in set(mine)}
        for pid in post_ids
    }
