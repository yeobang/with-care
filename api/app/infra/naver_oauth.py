"""네이버 로그인 (OAuth 2.0) — 인프라 전용.

Supabase가 네이버를 지원하지 않아 우리가 직접 처리한다.
토큰 교환·프로필 조회만 담당하고, 세션 발급은 local_jwt가 한다.
"""

import httpx

from app.config import settings

AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
PROFILE_URL = "https://openapi.naver.com/v1/nid/me"
TIMEOUT = 10


def configured() -> bool:
    return bool(settings.naver_client_id and settings.naver_client_secret)


def authorize_url(state: str, redirect_uri: str) -> str:
    return (
        f"{AUTH_URL}?response_type=code&client_id={settings.naver_client_id}"
        f"&redirect_uri={redirect_uri}&state={state}"
    )


def exchange(code: str, state: str) -> str:
    """인가 코드 → 액세스 토큰. 단일 시도 + timeout (재시도 루프 없음)."""
    res = httpx.get(
        TOKEN_URL,
        params={
            "grant_type": "authorization_code",
            "client_id": settings.naver_client_id,
            "client_secret": settings.naver_client_secret,
            "code": code,
            "state": state,
        },
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    token = res.json().get("access_token")
    if not token:
        raise ValueError("네이버 토큰 교환 실패")
    return token


def profile(access_token: str) -> dict:
    """{id, email, name, mobile} — mobile은 동의 항목이 허용된 경우에만 온다."""
    res = httpx.get(PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=TIMEOUT)
    res.raise_for_status()
    body = res.json()
    if body.get("resultcode") != "00":
        raise ValueError("네이버 프로필 조회 실패")
    return body.get("response", {})
