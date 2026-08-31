"""Supabase Storage 클라이언트 (인프라 전용 — 경계 룰: 도메인 규칙은 여기 두지 않는다).

세션 사진 버킷은 private. 접근은 항상 API의 멤버십 검증(I6)을 거친 서명 URL로만.
"""

import httpx

from app.config import settings

BUCKET = "session-photos"
SIGN_EXPIRES_SEC = 3600


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=f"{settings.supabase_url}/storage/v1",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "apikey": settings.supabase_service_key,  # sb_secret_ 키는 JWT가 아니라 apikey 헤더 필요
        },
        timeout=30,
    )


def ensure_bucket() -> None:
    with _client() as c:
        res = c.get(f"/bucket/{BUCKET}")
        if res.status_code == 200:
            return
        c.post("/bucket", json={"id": BUCKET, "name": BUCKET, "public": False}).raise_for_status()


def upload(path: str, content: bytes, content_type: str) -> None:
    ensure_bucket()
    with _client() as c:
        res = c.post(
            f"/object/{BUCKET}/{path}",
            content=content,
            headers={"Content-Type": content_type, "x-upsert": "false"},
        )
        res.raise_for_status()


def signed_urls(paths: list[str]) -> dict[str, str]:
    """여러 경로의 서명 URL을 한 번의 호출로 발급 — 사진 목록의 N+1 외부호출 회피."""
    if not paths:
        return {}
    with _client() as c:
        res = c.post(f"/object/sign/{BUCKET}", json={"paths": paths, "expiresIn": SIGN_EXPIRES_SEC})
        res.raise_for_status()
        return {
            item["path"]: f"{settings.supabase_url}/storage/v1{item['signedURL']}"
            for item in res.json()
            if item.get("signedURL")
        }
