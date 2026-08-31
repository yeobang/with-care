"""FastAPI 의존성: DB 세션, 현재 사용자.

인증 2경로 (P6):
- **Bearer JWT** (Supabase Auth, ES256/JWKS) — dev·prod 공통. prod의 유일한 경로
- **X-User-Id 헤더** — dev 한정 (로컬·테스트 편의)

본인인증(I1)은 로그인과 별개 축: users.identity_verified + POST /identity/verify
(infra/identity.py 어댑터 — PASS류 확보 시 교체).
"""

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.domain.models import User
from app.infra import auth_jwt

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
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> User:
    if authorization and authorization.lower().startswith("bearer "):
        claims = auth_jwt.verify(authorization[7:])
        user = db.get(User, claims["sub"])
        if user is None:
            # 계정은 있으나 프로필 미생성 — 앱은 이 코드를 받으면 가입(이름 입력)으로 보낸다
            raise HTTPException(status_code=401, detail="signup_required")
        return user
    if settings.env == "dev" and x_user_id:
        user = db.get(User, x_user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="알 수 없는 사용자")
        return user
    raise HTTPException(status_code=401, detail="인증 필요 (Bearer 토큰)")
