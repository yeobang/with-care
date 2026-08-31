"""Expo Push 발송 — 인프라 전용.

단일 시도 + timeout, 재시도 루프 없음 (외부 API 과도 호출 금지).
알림은 best-effort: 호출자(notifications)가 실패를 삼킨다 — 본 흐름을 깨지 않는다.
"""

import httpx

EXPO_URL = "https://exp.host/--/api/v2/push/send"
CHUNK = 100  # Expo 권장 배치 상한


def send(messages: list[dict]) -> list[dict]:
    """메시지 발송 → 티켓 목록(순서 보존). messages: [{to, title, body, ...}]."""
    if not messages:
        return []
    results: list[dict] = []
    with httpx.Client(timeout=10) as c:
        for i in range(0, len(messages), CHUNK):
            res = c.post(EXPO_URL, json=messages[i : i + CHUNK])
            res.raise_for_status()
            results.extend(res.json().get("data", []))
    return results
