from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.domain.models import PushToken, User

router = APIRouter(tags=["push"])


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/push/tokens")
def register_token(
    body: TokenIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Expo 푸시 토큰 등록 (upsert). 같은 기기의 주인이 바뀌면 이전 소유를 이관한다."""
    existing = db.scalar(select(PushToken).where(PushToken.token == body.token))
    if existing is not None:
        existing.user_id = user.id
    else:
        db.add(PushToken(user_id=user.id, token=body.token))
    db.flush()
    return {"ok": True}
