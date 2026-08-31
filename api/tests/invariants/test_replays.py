"""재호출·재탭·중복 요청 — 500으로 새지 않고 멱등하거나 도메인 오류로 떨어져야 한다.

대상 결함: propose 재호출 시 후보 중복 생성 / 중복 합류·중복 확정의 IntegrityError 500.
"""

import pytest
from sqlalchemy import select

from app.domain import board_service as board
from app.domain import crew_service as svc
from app.domain.models import Assignment, CareSession, Child, Consent, SlotKind


@pytest.fixture
def board_crew(db, verified_user):
    """활성화 완료 크루(오너+부모2) + 각 부모의 아이 + 보드 슬롯(가능 1, 필요 2)."""
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "보드크루")
    moms, kids = [], {}
    for i in range(2):
        m = verified_user(f"부모{i}")
        inv = svc.create_invite(db, crew.id, owner)
        svc.join_crew(db, m, inv.token)
        moms.append(m)
    for u in [owner, *moms]:
        svc.submit_consent(db, crew.id, u, liability_ack=True, photo_consent=True, guardian_consent=True)
    svc.confirm_charter(db, crew.id, owner)
    svc.activate_crew(db, crew.id, owner)
    date = "2026-09-07"
    board.add_slot(db, crew.id, owner, kind=SlotKind.AVAILABLE, date=date, start_hour=15, end_hour=17)
    for m in moms:
        child = Child(guardian_id=m.id, name="아이", birth_year_month="2022-05", emergency_contact="010")
        db.add(child)
        db.flush()
        kids[m.id] = child
        board.add_slot(db, crew.id, m, kind=SlotKind.NEED, date=date, start_hour=15, end_hour=17, child_id=child.id)
    return crew, owner, moms, date


def _count_assignments(db, crew_id, date):
    return len(db.scalars(
        select(Assignment).where(Assignment.crew_id == crew_id, Assignment.date == date)
    ).all())


def test_propose_recall_is_idempotent(db, board_crew):
    """propose 재호출(연타) 시 후보가 중복 생성되지 않는다."""
    crew, owner, moms, date = board_crew
    board.propose_assignments(db, crew.id, owner, date)
    n1 = _count_assignments(db, crew.id, date)
    board.propose_assignments(db, crew.id, owner, date)
    board.propose_assignments(db, crew.id, owner, date)
    assert _count_assignments(db, crew.id, date) == n1


def test_propose_recall_preserves_partial_confirmation(db, board_crew):
    """일부 가정이 이미 확정 탭을 누른 후보는 재호출에 지워지지 않는다 (I4의 탭은 소급 소실 금지)."""
    crew, owner, moms, date = board_crew
    [prop] = board.propose_assignments(db, crew.id, owner, date)
    board.confirm_assignment(db, prop.id, moms[0])  # 부분 확정 (전원 아님 → 세션 없음)
    board.propose_assignments(db, crew.id, owner, date)
    kept = db.get(Assignment, prop.id)
    assert kept is not None
    confirmed_flags = [r.guardian_confirmed for r in kept.children]
    assert any(confirmed_flags) and not all(confirmed_flags)
    assert _count_assignments(db, crew.id, date) == 1  # 동일 후보 중복 생성도 없음


def test_confirm_retap_after_session_is_idempotent(db, board_crew):
    """전원 확정으로 세션이 생긴 뒤의 재탭 — 같은 세션을 돌려주고 중복 세션을 만들지 않는다."""
    crew, owner, moms, date = board_crew
    [prop] = board.propose_assignments(db, crew.id, owner, date)
    board.confirm_assignment(db, prop.id, moms[0])
    session = board.confirm_assignment(db, prop.id, moms[1])
    assert session is not None
    again = board.confirm_assignment(db, prop.id, moms[1])
    assert again is not None and again.id == session.id
    sessions = db.scalars(select(CareSession).where(CareSession.crew_id == crew.id)).all()
    assert len(sessions) == 1


def test_double_join_is_domain_error(db, verified_user):
    """이미 멤버인 사용자의 재합류는 IntegrityError(500)가 아니라 도메인 오류(422)로."""
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    mom = verified_user("부모")
    inv1 = svc.join_crew(db, mom, svc.create_invite(db, crew.id, owner).token)
    assert inv1 is not None
    inv2 = svc.create_invite(db, crew.id, owner)
    with pytest.raises(ValueError):
        svc.join_crew(db, mom, inv2.token)
    # 실패한 시도가 초대장을 소모하지 않는다
    from app.domain.models import Invite
    assert db.get(Invite, inv2.token).used_by is None


def test_resubmit_consent_updates_not_crashes(db, verified_user):
    """합의 재제출(재동의 경로)은 기존 행 갱신 — UniqueConstraint 500이 아니다."""
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "크루")
    svc.submit_consent(db, crew.id, owner, liability_ack=True, photo_consent=True, guardian_consent=True)
    first = db.scalar(select(Consent).where(Consent.crew_id == crew.id))
    t1 = first.consented_at
    svc.submit_consent(db, crew.id, owner, liability_ack=True, photo_consent=True, guardian_consent=True)
    rows = db.scalars(select(Consent).where(Consent.crew_id == crew.id)).all()

    def _utc(dt):  # SQLite 왕복은 tz를 벗긴다 — 비교 전 정규화
        from datetime import timezone
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    assert len(rows) == 1 and _utc(rows[0].consented_at) >= _utc(t1)
