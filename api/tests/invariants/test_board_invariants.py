"""I3·I4 불변식 테스트 (P2 주간 보드) — 위반 시도 → 차단 검증."""

import pytest
from sqlalchemy import select

from app.domain import board_service as board
from app.domain import crew_service as svc
from app.domain.errors import HumanChoiceViolation, UnlicensedCarePattern
from app.domain.models import CareSession, Child, SlotKind, User

DATE = "2026-09-07"


@pytest.fixture
def crew_with_families(db, verified_user):
    """활성 크루 빌더 + 아이 생성 헬퍼."""

    def _build(n_members: int):
        owner = verified_user("가구0")
        crew = svc.create_crew(db, owner, "크루")
        users = [owner]
        for i in range(1, n_members):
            u = verified_user(f"가구{i}")
            invite = svc.create_invite(db, crew.id, owner)
            svc.join_crew(db, u, invite.token)
            users.append(u)
        for u in users:
            svc.submit_consent(db, crew.id, u, liability_ack=True, photo_consent=True, guardian_consent=True)
        svc.confirm_charter(db, crew.id, owner)
        svc.activate_crew(db, crew.id, owner)
        return crew.id, users

    def _child(guardian: User, birth: str = "2022-05") -> Child:
        c = Child(guardian_id=guardian.id, name="아이", birth_year_month=birth, emergency_contact="010")
        db.add(c)
        db.flush()
        return c

    return _build, _child


def _setup_needs(db, crew_id, caregiver, families_with_children):
    board.add_slot(db, crew_id, caregiver, kind=SlotKind.AVAILABLE, date=DATE, start_hour=14, end_hour=18)
    for user, child in families_with_children:
        board.add_slot(
            db, crew_id, user, kind=SlotKind.NEED,
            date=DATE, start_hour=15, end_hour=17, child_id=child.id,
        )


def _confirm_all(db, proposal, guardians):
    result = None
    for g in guardians:
        result = board.confirm_assignment(db, proposal.id, g)
    return result


# --- I4: 고르기는 사람 ---


def test_i4_proposal_has_no_effect(db, crew_with_families):
    build, child = crew_with_families
    crew_id, users = build(3)
    _setup_needs(db, crew_id, users[0], [(u, child(u)) for u in users[1:]])
    proposals = board.propose_assignments(db, crew_id, users[0], DATE)
    assert len(proposals) == 1
    assert db.scalars(select(CareSession)).all() == []  # 후보 나열 ≠ 세션


def test_i4_session_only_after_all_families_confirm(db, crew_with_families):
    build, child = crew_with_families
    crew_id, users = build(3)
    kids = [(u, child(u)) for u in users[1:]]
    _setup_needs(db, crew_id, users[0], kids)
    [proposal] = board.propose_assignments(db, crew_id, users[0], DATE)

    assert board.confirm_assignment(db, proposal.id, users[1]) is None  # 부분 확정 = 효력 없음
    session = board.confirm_assignment(db, proposal.id, users[2])
    assert session is not None
    assert session.caregiver_id == users[0].id


def test_i4_cannot_confirm_for_others_child(db, crew_with_families):
    build, child = crew_with_families
    crew_id, users = build(3)
    _setup_needs(db, crew_id, users[0], [(users[1], child(users[1]))])
    [proposal] = board.propose_assignments(db, crew_id, users[0], DATE)
    with pytest.raises(HumanChoiceViolation):
        board.confirm_assignment(db, proposal.id, users[2])  # 남의 아이 배정을 대신 확정 시도


def test_i4_multiple_caregivers_yield_multiple_candidates(db, crew_with_families):
    """단일 추천 금지 — 가능한 돌봄자가 둘이면 후보도 둘."""
    build, child = crew_with_families
    crew_id, users = build(3)
    board.add_slot(db, crew_id, users[0], kind=SlotKind.AVAILABLE, date=DATE, start_hour=14, end_hour=18)
    board.add_slot(db, crew_id, users[1], kind=SlotKind.AVAILABLE, date=DATE, start_hour=14, end_hour=18)
    c = child(users[2])
    board.add_slot(db, crew_id, users[2], kind=SlotKind.NEED, date=DATE, start_hour=15, end_hour=17, child_id=c.id)
    proposals = board.propose_assignments(db, crew_id, users[0], DATE)
    assert len(proposals) == 2


# --- I3: 무인가 보육 패턴 차단 ---


def test_i3_five_preschoolers_blocked(db, crew_with_families):
    build, child = crew_with_families
    crew_id, users = build(6)
    kids = [(u, child(u, birth="2022-05")) for u in users[1:]]  # 타인 영유아 5명
    _setup_needs(db, crew_id, users[0], kids)
    [proposal] = board.propose_assignments(db, crew_id, users[0], DATE)
    with pytest.raises(UnlicensedCarePattern):
        _confirm_all(db, proposal, [u for u, _ in kids])


def test_i3_four_preschoolers_allowed(db, crew_with_families):
    build, child = crew_with_families
    crew_id, users = build(5)
    kids = [(u, child(u, birth="2022-05")) for u in users[1:]]  # 타인 영유아 4명
    _setup_needs(db, crew_id, users[0], kids)
    [proposal] = board.propose_assignments(db, crew_id, users[0], DATE)
    session = _confirm_all(db, proposal, [u for u, _ in kids])
    assert session is not None


def test_i3_elementary_children_not_counted(db, crew_with_families):
    """초등생(취학 연령)은 영유아 카운트에서 제외 — 총 5명이어도 허용."""
    build, child = crew_with_families
    crew_id, users = build(6)
    kids = [(u, child(u, birth="2022-05")) for u in users[1:4]]  # 영유아 3
    kids += [(u, child(u, birth="2017-03")) for u in users[4:]]  # 초등 2
    _setup_needs(db, crew_id, users[0], kids)
    [proposal] = board.propose_assignments(db, crew_id, users[0], DATE)
    session = _confirm_all(db, proposal, [u for u, _ in kids])
    assert session is not None
