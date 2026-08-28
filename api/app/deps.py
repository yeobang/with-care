"""FastAPI 의존성: DB 세션, 현재 사용자.

⚠️ 인증은 dev 모드 한정 헤더 방식(X-User-Id). Supabase Auth JWT 검증으로 교체 전에는
정식 배포 불가 (docs/02-guardrails.md 법률 게이트와 별개의 기술 게이트).
"""

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.domain.models import User

_engine = create_engine(settings.database_url, pool_pre_ping=True)
_SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    x_user_id: str | None = Header(default=None),
) -> User:
    if settings.env != "dev":
        raise HTTPException(status_code=501, detail="prod 인증(Supabase JWT) 미구현 — 배포 게이트")
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id 헤더 필요 (dev)")
    user = db.get(User, x_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="알 수 없는 사용자")
    return user
