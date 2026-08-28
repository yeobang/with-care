"""불변식 테스트 (CLAUDE.md: 문서에만 있는 불변식은 죽은 불변식이다).

각 테스트는 위반을 '시도'하고 시스템이 막는지 검증한다.
I3·I4·I5는 해당 구현 단계(P2·P4)에서 전환 — 그 전까지 xfail로 등록 유지.
"""

import pytest

from app.domain import crew_service as svc
from app.domain.errors import (
    CharterIncomplete,
    ConsentMissing,
    CrewIsolationViolation,
    HandoffGateViolation,
)
from app.domain.models import User

PENDING = pytest.mark.xfail(reason="구현 단계 도달 전 (docs/03-dev-plan.md)", strict=False)


# --- I1: 본인인증 + 크루 초대 없이는 인계 불가 (P1 절반: 멤버십 관문) ---

def test_i1_unverified_user_cannot_create_crew(db):
    stranger = User(name="미인증", identity_verified=False)
    db.add(stranger)
    db.flush()
    with pytest.raises(HandoffGateViolation):
        svc.create_crew(db, stranger, "몰래크루")


def test_i1_unverified_user_cannot_join(db, verified_user, active_crew):
    crew, owner = active_crew
    invite = svc.create_invite(db, crew.id, owner)
    stranger = User(name="미인증", identity_verified=False)
    db.add(stranger)
    db.flush()
    with pytest.raises(HandoffGateViolation):
        svc.join_crew(db, stranger, invite.token)


def test_i1_no_join_without_invite(db, verified_user):
    outsider = verified_user("인증됐지만초대없음")
    with pytest.raises(HandoffGateViolation):
        svc.join_crew(db, outsider, "존재하지-않는-토큰")


def test_i1_invite_is_single_use(db, verified_user, active_crew):
    crew, owner = active_crew
    invite = svc.create_invite(db, crew.id, owner)
    svc.join_crew(db, verified_user("첫사용자"), invite.token)
    with pytest.raises(HandoffGateViolation):
        svc.join_crew(db, verified_user("재사용시도"), invite.token)


# --- I2: 포괄 합의 없이는 크루 활동 시작 불가 ---

def test_i2_partial_consent_rejected(db, verified_user):
    owner = verified_user()
    crew = svc.create_crew(db, owner, "크루")
    with pytest.raises(ConsentMissing):
        svc.submit_consent(db, crew.id, owner, liability_ack=True, photo_consent=False, guardian_consent=True)


def test_i2_activation_blocked_until_all_members_consent(db, verified_user):
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    svc.confirm_charter(db, crew.id, owner)
    svc.submit_consent(db, crew.id, owner, liability_ack=True, photo_consent=True, guardian_consent=True)
    invite = svc.create_invite(db, crew.id, owner)
    svc.join_crew(db, verified_user("합의안한멤버"), invite.token)
    with pytest.raises(ConsentMissing):
        svc.activate_crew(db, crew.id, owner)


# --- I6: 크루 데이터는 크루 밖으로 나가지 않는다 ---

def test_i6_nonmember_cannot_view_crew(db, verified_user, active_crew):
    crew, _ = active_crew
    outsider = verified_user("남의크루엿보기")
    with pytest.raises(CrewIsolationViolation):
        svc.get_crew_view(db, crew.id, outsider)


def test_i6_member_of_other_crew_cannot_view(db, verified_user, active_crew):
    crew, _ = active_crew
    other_owner = verified_user("다른크루오너")
    svc.create_crew(db, other_owner, "다른크루")
    with pytest.raises(CrewIsolationViolation):
        svc.get_crew_view(db, crew.id, other_owner)


def test_i6_nonmember_cannot_invite(db, verified_user, active_crew):
    crew, _ = active_crew
    outsider = verified_user("외부인")
    with pytest.raises(CrewIsolationViolation):
        svc.create_invite(db, crew.id, outsider)


# --- I7: 규약 없는 크루는 활성화되지 않는다 ---

def test_i7_activation_blocked_without_charter_confirm(db, verified_user):
    owner = verified_user()
    crew = svc.create_crew(db, owner, "크루")
    svc.submit_consent(db, crew.id, owner, liability_ack=True, photo_consent=True, guardian_consent=True)
    with pytest.raises(CharterIncomplete):
        svc.activate_crew(db, crew.id, owner)


def test_i7_charter_created_with_defaults(db, verified_user):
    """백지 협상 금지 — 크루 생성 즉시 규약이 기본값으로 존재해야 한다."""
    from sqlalchemy import select
    from app.domain.models import Charter

    owner = verified_user()
    crew = svc.create_crew(db, owner, "크루")
    charter = db.scalar(select(Charter).where(Charter.crew_id == crew.id))
    assert charter is not None
    assert charter.credit_price_krw > 0
    assert not charter.is_complete  # 기본값 존재 ≠ 합의 완료


# --- I8: 연령 분기 금지 (정적 트립와이어) ---

def test_i8_no_age_branching_in_domain_source():
    """도메인 소스에 연령 조건 분기가 없어야 한다.

    허용 예외(가드레일 §2): 0~2세 보류 플래그, I3의 영유아 카운트.
    예외를 추가하려면 이 테스트의 ALLOWED에 근거 주석과 함께 등록해야 한다 — 그게 리뷰 지점.
    """
    import pathlib
    import re

    domain_dir = pathlib.Path(__file__).parents[2] / "app" / "domain"
    ALLOWED: set[str] = set()  # 예: "session_service.py:42  # I3 영유아 카운트"
    pattern = re.compile(r"\b(age|나이|개월수)\b.*(if|<|>|==)|"
                         r"(if|<|>|==).*\b(age|나이|개월수)\b")
    violations = []
    for f in domain_dir.glob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and f"{f.name}:{i}" not in ALLOWED:
                violations.append(f"{f.name}:{i}: {line.strip()}")
    assert not violations, f"연령 분기 발견 (I8): {violations}"


# --- 구현 단계 미도달 (P2·P4에서 전환) ---

@PENDING
def test_i3_unlicensed_care_pattern_blocked():
    """I3: 돌봄자 1인 + 타인 영유아 5인 이상 세션 생성 불가. (P2)"""
    raise NotImplementedError


@PENDING
def test_i4_humans_choose():
    """I4: 배정·시터 선택은 복수 후보 중 명시적 확정 탭. (P2)"""
    raise NotImplementedError


@PENDING
def test_i5_no_money_in_neighbor_track():
    """I5: 크레딧 환급·이체 실행 코드 부재 검증. (P4)"""
    raise NotImplementedError
