"""커뮤니티 API (§27). 익명 글은 응답에서 작성자를 가린다 (서버는 알되 노출 안 함)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain import community_service as cs
from app.domain.models import Comment, Post, PostCategory, PostScope, User

router = APIRouter(tags=["community"])


class TownIn(BaseModel):
    town_code: str = Field(min_length=2, max_length=20)
    town_name: str = Field(min_length=1, max_length=50)


@router.patch("/me/town")
def set_town(body: TownIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """동네 설정 — 행정동까지만 (좌표·상세주소는 받지 않는다)."""
    user.town_code = body.town_code
    user.town_name = body.town_name
    db.flush()
    return {"town_code": user.town_code, "town_name": user.town_name}


class PostIn(BaseModel):
    scope: PostScope = PostScope.TOWN
    category: PostCategory = PostCategory.QUESTION
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)
    crew_id: str | None = None
    anonymous: bool = False


@router.post("/posts")
def create_post(body: PostIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = cs.create_post(db, user, **body.model_dump())
    return _post_out(db, post, user, cs.stats(db, [post.id], user))


@router.get("/posts")
def feed(
    scope: PostScope = PostScope.TOWN,
    crew_id: str | None = None,
    category: str | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    posts = (
        cs.crew_feed(db, crew_id, user, limit)
        if scope == PostScope.CREW and crew_id
        else cs.town_feed(db, user, category=category, limit=limit)
    )
    st = cs.stats(db, [p.id for p in posts], user)
    return [_post_out(db, p, user, st) for p in posts]


@router.get("/posts/{post_id}")
def post_detail(post_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = cs.get_post(db, post_id, user)
    st = cs.stats(db, [post.id], user)
    return {
        **_post_out(db, post, user, st),
        "comments": [_comment_out(db, c, user) for c in cs.comments_of(db, post_id, user)],
    }


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    anonymous: bool = False


@router.post("/posts/{post_id}/comments")
def add_comment(post_id: str, body: CommentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = cs.add_comment(db, post_id, user, body.body, body.anonymous)
    return _comment_out(db, c, user)


@router.post("/posts/{post_id}/like")
def like(post_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count, liked = cs.toggle_like(db, post_id, user)
    return {"likes": count, "liked": liked}


@router.delete("/posts/{post_id}")
def delete_post(post_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cs.delete_post(db, post_id, user)
    return {"ok": True}


def _author(db: Session, author_id: str, anonymous: bool, me: User) -> dict:
    """익명이면 작성자를 가린다. 본인에게만 '나(익명)'로 보인다."""
    if anonymous:
        return {"id": None, "name": "익명", "is_me": author_id == me.id}
    u = db.get(User, author_id)
    return {"id": author_id, "name": u.name if u else "알 수 없음", "is_me": author_id == me.id}


def _post_out(db: Session, p: Post, me: User, st: dict) -> dict:
    s = st.get(p.id, {"likes": 0, "comments": 0, "liked": False})
    return {
        "id": p.id,
        "scope": str(p.scope),
        "category": str(p.category),
        "title": p.title,
        "body": p.body,
        "author": _author(db, p.author_id, p.anonymous, me),
        "created_at": p.created_at.isoformat(),
        "likes": s["likes"],
        "liked": s["liked"],
        "comment_count": s["comments"],
        "town_name": db.get(User, p.author_id).town_name if p.scope == PostScope.TOWN else None,
    }


def _comment_out(db: Session, c: Comment, me: User) -> dict:
    return {
        "id": c.id,
        "body": c.body,
        "author": _author(db, c.author_id, c.anonymous, me),
        "created_at": c.created_at.isoformat(),
    }
