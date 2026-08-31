"""본인인증 어댑터 (I1의 실물 관문) — 인프라 전용.

결정(dev-plan 확정 2, 2026-08-31): 사업자 미확보 → PASS류 실연동 전까지 스텁.
연동처가 생기면 이 인터페이스 뒤에서만 교체한다 — 도메인·라우터는 무변경.
"""

from typing import Protocol


class IdentityVerifier(Protocol):
    def verify(self, user_id: str, name: str) -> bool:
        """본인인증 시도. True = 인증 성공."""
        ...


class StubVerifier:
    """항상 승인하는 스텁. 정식 출시 전 실제 구현으로 교체 필수 (배포 게이트)."""

    def verify(self, user_id: str, name: str) -> bool:
        return True


def get_verifier() -> IdentityVerifier:
    # TODO(PASS 연동 시): settings 값으로 분기
    return StubVerifier()
