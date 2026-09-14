"""본인인증 어댑터 (I1의 실물 관문) — 인프라 전용.

인증 수단은 환경설정으로 고른다 (키가 있는 것만 켠다):
- phone : Supabase 전화 OTP(SMS)로 확인된 계정만 통과 — JWT의 phone_confirmed_at 근거
- email : 메일 확인을 마친 계정만 통과 — JWT의 email_confirmed_at 근거
- stub  : 무조건 통과 (개발용. 정식 출시 전 반드시 phone 또는 PASS로 교체)

PASS(통신사 본인확인)는 사업자등록·계약이 필요해 확보 시 PassVerifier로 추가한다.
이 인터페이스 뒤에서만 교체하면 도메인·라우터는 그대로다.
"""

from typing import Protocol

from app.config import settings


class IdentityVerifier(Protocol):
    def verify(self, claims: dict) -> tuple[bool, str]:
        """(통과 여부, 사용자에게 보일 사유)."""
        ...


class StubVerifier:
    """개발용 — 무조건 통과. 배포 게이트: prod에서는 쓰지 않는다."""

    def verify(self, claims: dict) -> tuple[bool, str]:
        return True, "dev"


class PhoneVerifier:
    """전화 OTP 확인 계정만 통과. Supabase가 SMS 검증을 끝낸 사실을 JWT로 확인한다."""

    def verify(self, claims: dict) -> tuple[bool, str]:
        if claims.get("phone_confirmed_at") or (claims.get("phone") and claims.get("phone_verified")):
            return True, "phone"
        return False, "휴대폰 인증을 먼저 완료해주세요"


class EmailVerifier:
    """메일 확인 계정만 통과 (전화 인증 도입 전의 최소선)."""

    def verify(self, claims: dict) -> tuple[bool, str]:
        confirmed = claims.get("email_confirmed_at") or claims.get("email_verified")
        if confirmed:
            return True, "email"
        return False, "이메일 인증을 먼저 완료해주세요"


_VERIFIERS = {"stub": StubVerifier, "phone": PhoneVerifier, "email": EmailVerifier}


def get_verifier() -> IdentityVerifier:
    return _VERIFIERS.get(settings.identity_method, StubVerifier)()
