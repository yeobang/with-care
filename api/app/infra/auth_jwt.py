"""Supabase Auth JWT 검증 (ES256/JWKS) — 인프라 전용.

계정 인증(로그인)과 본인인증(I1)은 별개 축이다:
여기는 "누가 로그인했는가"만 답하고, 본인인증은 infra/identity.py 어댑터가 담당한다.

실패 전략: 검증은 fail-closed(401). JWKS 조회는 timeout + 캐시 — 인증 서버가 잠깐
죽어도 캐시된 키로 검증을 계속한다(키 회전 주기 대비 TTL 10분).
"""

import time

import httpx
import jwt
from fastapi import HTTPException

from app.config import settings

_JWKS_TTL_SEC = 600
_cache: dict = {"keys": None, "at": 0.0}


def _jwks() -> dict:
    now = time.monotonic()
    if _cache["keys"] is not None and now - _cache["at"] <= _JWKS_TTL_SEC:
        return _cache["keys"]
    try:
        res = httpx.get(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", timeout=10
        )
        res.raise_for_status()
        _cache.update(keys=res.json(), at=now)
    except httpx.HTTPError:
        if _cache["keys"] is not None:
            return _cache["keys"]  # degrade: 갱신 실패 시 캐시로 계속
        raise HTTPException(status_code=503, detail="인증 키를 확인할 수 없다")
    return _cache["keys"]


def verify(token: str) -> dict:
    """토큰 검증 → claims. 서명·만료·오디언스 어느 하나라도 틀리면 401 (fail-closed)."""
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = next(k for k in _jwks()["keys"] if k.get("kid") == kid)
        return jwt.decode(
            token, jwt.PyJWK(key).key, algorithms=["ES256"], audience="authenticated"
        )
    except (StopIteration, jwt.PyJWTError, KeyError):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
