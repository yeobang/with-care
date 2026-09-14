"""네이버 로그인 라우터 — Supabase 미지원 제공자의 자체 처리 경로."""

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.domain.models import User
from app.infra import local_jwt, naver_oauth

router = APIRouter(tags=["oauth"])

# state는 CSRF 방지용 1회성 값 — 메모리 보관(상한 있음), 서버 재시작 시 비어도 재로그인이면 된다
_states: dict[str, float] = {}
_STATE_MAX = 500


def _callback_uri() -> str:
    return f"{settings.web_origin.rstrip('/')}/auth/naver/callback"


@router.get("/auth/providers")
def providers():
    """앱이 어떤 소셜 버튼을 그릴지 판단 (Supabase 제공자는 앱이 직접 조회)."""
    return {"naver": naver_oauth.configured() and bool(settings.jwt_secret)}


@router.get("/auth/naver/start")
def naver_start():
    if not (naver_oauth.configured() and settings.jwt_secret):
        raise HTTPException(status_code=503, detail="네이버 로그인이 구성되지 않았어요")
    import time

    if len(_states) > _STATE_MAX:  # 오래된 것부터 정리
        for k in sorted(_states, key=_states.get)[: _STATE_MAX // 2]:
            _states.pop(k, None)
    state = secrets.token_urlsafe(24)
    _states[state] = time.time()
    return RedirectResponse(naver_oauth.authorize_url(state, _callback_uri()))


@router.get("/auth/naver/callback")
def naver_callback(code: str, state: str, db: Session = Depends(get_db)):
    """인가 코드 → 프로필 → 우리 JWT 발급 → 웹으로 토큰 전달."""
    if _states.pop(state, None) is None:
        raise HTTPException(status_code=400, detail="만료되었거나 잘못된 요청이에요")

    access = naver_oauth.exchange(code, state)
    prof = naver_oauth.profile(access)
    naver_id = prof.get("id")
    if not naver_id:
        raise HTTPException(status_code=502, detail="네이버 프로필을 확인할 수 없어요")

    uid = local_jwt.user_id_for("naver", naver_id)
    user = db.get(User, uid)
    token = local_jwt.issue(
        sub=uid,
        email=prof.get("email"),
        phone=prof.get("mobile"),
        provider="naver",
    )
    # 프로필이 없으면 앱이 이름 입력 단계로 보낸다 (Supabase 경로와 동일한 규칙)
    suffix = "" if user else "&signup=1"
    name = prof.get("name") or ""
    return RedirectResponse(f"{settings.web_origin.rstrip('/')}/#token={token}{suffix}&name={name}")
