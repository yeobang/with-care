"""P8 보드 완성: 인접 슬롯 병합 · 빈칸 감지 · 배정 거절 (I4의 거절 반쪽)."""

import pytest
from sqlalchemy import select

from app.domain import board_service as board
from app.domain import crew_service as svc
from app.domain import errors
from app.domain.models import Assignment, Child, SlotKind


@pytest.fixture
def crew3(db, verified_user):
    """활성 크루: 오너 + 부모2, 부모마다 아이 1."""
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "P8크루")
    moms, kids = [], {}
    for i in range(2):
        m = verified_user(f"부모{i}")
        svc.join_crew(db, m, svc.create_invite(db, crew.id, owner).token)
        moms.append(m)
    for u in [owner, *moms]:
        svc.submit_consent(db, crew.id, u, liability_ack=True, photo_consent=True, guardian_consent=True)
    svc.confirm_charter(db, crew.id, owner)
    svc.activate_crew(db, crew.id, owner)
    for m in moms:
        child = Child(guardian_id=m.id, name="아이", birth_year_month="2022-05", emergency_contact="010")
        db.add(child)
        db.flush()
        kids[m.id] = child
    return crew, owner, moms, kids


DATE = "2026-09-07"


def _slot(db, crew, user, kind, start, end, child_id=None, date=DATE):
    return board.add_slot(db, crew.id, user, kind=kind, date=date,
                          start_hour=start, end_hour=end, child_id=child_id)


# --- 인접 슬롯 병합 ---


def test_adjacent_avail_slots_cover_long_need(db, crew3):
    """1시간 가능 슬롯 3개(14-15,15-16,16-17)가 14-17 필요를 커버한다 (병합)."""
    crew, owner, (mom, _), kids = crew3
    for h in (14, 15, 16):
        _slot(db, crew, owner, SlotKind.AVAILABLE, h, h + 1)
    _slot(db, crew, mom, SlotKind.NEED, 14, 17, kids[mom.id].id)
    [p] = board.propose_assignments(db, crew.id, owner, DATE)
    assert (p.start_hour, p.end_hour) == (14, 17)


def test_adjacent_need_slots_merge(db, crew3):
    """같은 아이의 필요 슬롯 15-16 + 16-17 은 15-17 한 구간으로 병합돼 후보도 하나다."""
    crew, owner, (mom, _), kids = crew3
    _slot(db, crew, owner, SlotKind.AVAILABLE, 14, 18)
    _slot(db, crew, mom, SlotKind.NEED, 15, 16, kids[mom.id].id)
    _slot(db, crew, mom, SlotKind.NEED, 16, 17, kids[mom.id].id)
    [p] = board.propose_assignments(db, crew.id, owner, DATE)
    assert (p.start_hour, p.end_hour) == (15, 17)


def test_non_adjacent_not_merged(db, crew3):
    """14-15와 16-17은 병합되지 않는다 — 14-17 필요는 후보 없이 빈칸."""
    crew, owner, (mom, _), kids = crew3
    _slot(db, crew, owner, SlotKind.AVAILABLE, 14, 15)
    _slot(db, crew, owner, SlotKind.AVAILABLE, 16, 17)
    _slot(db, crew, mom, SlotKind.NEED, 14, 17, kids[mom.id].id)
    assert board.propose_assignments(db, crew.id, owner, DATE) == []
    [gap] = board.find_gaps(db, crew.id, owner, DATE)
    assert (gap["start_hour"], gap["end_hour"]) == (14, 17)


# --- 빈칸 감지 ---


def test_gap_cleared_when_avail_added(db, crew3):
    crew, owner, (mom, _), kids = crew3
    _slot(db, crew, mom, SlotKind.NEED, 15, 17, kids[mom.id].id)
    assert len(board.find_gaps(db, crew.id, owner, DATE)) == 1
    _slot(db, crew, owner, SlotKind.AVAILABLE, 15, 17)
    assert board.find_gaps(db, crew.id, owner, DATE) == []


def test_partial_coverage_is_still_gap(db, crew3):
    """부분 커버(14-16 가능 vs 14-17 필요)는 빈칸이다 — 반쪽 돌봄 불성립."""
    crew, owner, (mom, _), kids = crew3
    _slot(db, crew, owner, SlotKind.AVAILABLE, 14, 16)
    _slot(db, crew, mom, SlotKind.NEED, 14, 17, kids[mom.id].id)
    assert len(board.find_gaps(db, crew.id, owner, DATE)) == 1


def test_own_avail_does_not_cover_own_need(db, crew3):
    """자기 가능시간은 자기 아이 필요를 커버하지 않는다 (자기 돌봄은 빈칸 해소가 아님)."""
    crew, owner, (mom, _), kids = crew3
    _slot(db, crew, mom, SlotKind.AVAILABLE, 14, 18)
    _slot(db, crew, mom, SlotKind.NEED, 15, 17, kids[mom.id].id)
    assert len(board.find_gaps(db, crew.id, owner, DATE)) == 1


# --- 거절 흐름 ---


def test_decline_by_guardian_and_no_regeneration(db, crew3):
    crew, owner, (mom_b, mom_c), kids = crew3
    _slot(db, crew, owner, SlotKind.AVAILABLE, 15, 17)
    for m in (mom_b, mom_c):
        _slot(db, crew, m, SlotKind.NEED, 15, 17, kids[m.id].id)
    [p] = board.propose_assignments(db, crew.id, owner, DATE)

    declined = board.decline_assignment(db, p.id, mom_b)
    assert str(declined.status) == "declined"
    # 거절된 후보는 확정 불가
    with pytest.raises(ValueError):
        board.confirm_assignment(db, p.id, mom_c)
    # 재제안해도 동일 후보는 다시 만들지 않는다
    board.propose_assignments(db, crew.id, owner, DATE)
    rows = db.scalars(select(Assignment).where(Assignment.crew_id == crew.id)).all()
    assert len(rows) == 1
    # 재탭 멱등
    assert str(board.decline_assignment(db, p.id, mom_b).status) == "declined"


def test_decline_by_caregiver_allowed(db, crew3):
    crew, owner, (mom_b, _), kids = crew3
    _slot(db, crew, owner, SlotKind.AVAILABLE, 15, 17)
    _slot(db, crew, mom_b, SlotKind.NEED, 15, 17, kids[mom_b.id].id)
    [p] = board.propose_assignments(db, crew.id, owner, DATE)
    assert str(board.decline_assignment(db, p.id, owner).status) == "declined"


def test_decline_by_unrelated_member_blocked(db, crew3):
    """관련 없는 멤버는 남의 후보를 거절할 수 없다 (I4)."""
    crew, owner, (mom_b, mom_c), kids = crew3
    _slot(db, crew, owner, SlotKind.AVAILABLE, 15, 17)
    _slot(db, crew, mom_b, SlotKind.NEED, 15, 17, kids[mom_b.id].id)
    [p] = board.propose_assignments(db, crew.id, owner, DATE)
    with pytest.raises(errors.HumanChoiceViolation):
        board.decline_assignment(db, p.id, mom_c)


def test_confirmed_assignment_cannot_be_declined(db, crew3):
    crew, owner, (mom_b, _), kids = crew3
    _slot(db, crew, owner, SlotKind.AVAILABLE, 15, 17)
    _slot(db, crew, mom_b, SlotKind.NEED, 15, 17, kids[mom_b.id].id)
    [p] = board.propose_assignments(db, crew.id, owner, DATE)
    assert board.confirm_assignment(db, p.id, mom_b) is not None
    with pytest.raises(ValueError):
        board.decline_assignment(db, p.id, mom_b)
