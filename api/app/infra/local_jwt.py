"""자체 JWT 발급자 — Supabase가 지원하지 않는 제공자(네이버)용.

Supabase Auth는 그대로 두고, 네이버로 들어온 사용자만 우리가 서명한 토큰을 준다.
검증은 auth_jwt가 iss로 갈라 처리한다 (Supabase JWKS | 우리 키).

보안: 비밀키는 환경변수에서만 온다. 없으면 발급·검증 모두 거부한다 (fail-closed).
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException

from app.config import settings

ISSUER = "with-care"
ALGO = "HS256"
TTL = timedelta(hours=12)
# 같은 네이버 계정이 항상 같은 사용자 id가 되도록 결정적으로 파생한다 (매핑 테이블 불필요)
_NS = uuid.UUID("6f1c1f4a-8f4a-4a3b-9c2e-7d5b1a0e9c11")


def _secret() -> str:
    if not settings.jwt_secret:
        raise HTTPException(status_code=503, detail="자체 인증이 구성되지 않았어요")
    return settings.jwt_secret


def user_id_for(provider: str, subject: str) -> str:
    return str(uuid.uuid5(_NS, f"{provider}:{subject}"))


def issue(*, sub: str, email: str | None, phone: str | None, provider: str) -> str:
    """앱이 쓸 액세스 토큰. 클레임은 Supabase 토큰과 같은 모양으로 맞춘다."""
    now = datetime.now(timezone.utc)
    claims: dict = {
        "sub": sub,
        "aud": "authenticated",
        "iss": ISSUER,
        "provider": provider,
        "iat": int(now.timestamp()),
        "exp": int((now + TTL).timestamp()),
    }
    if email:
        claims["email"] = email
        claims["email_confirmed_at"] = now.isoformat()  # 네이버가 확인한 메일
    if phone:
        # 네이버 계정은 휴대폰 본인확인을 거친다 — I1의 phone 수단으로 인정 (근거: §26)
        claims["phone"] = phone
        claims["phone_confirmed_at"] = now.isoformat()
    return jwt.encode(claims, _secret(), algorithm=ALGO)


def verify(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGO], audience="authenticated", issuer=ISSUER)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
