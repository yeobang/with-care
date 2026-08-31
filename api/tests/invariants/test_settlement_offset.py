"""정산 확정의 장부 상쇄 (§22) — 정산 이중 계산 결함의 회귀 테스트.

시나리오(결정 대장 §22): 8월 정산 확정 후 9월 세션 → 9월 정산에 8월 몫이 다시 나오면 안 된다.
"""

import pytest

from app.domain import board_service as board
from app.domain import crew_service as svc
from app.domain import ledger_service as ledger
from app.domain.models import Child, SlotKind


@pytest.fixture
def credit_crew(db, verified_user):
    """정산모드 credit(단가 10000원) 크루: 오너 + 부모 2가구, 전원 합의·활성화 완료."""
    owner = verified_user("오너")
    crew = svc.create_crew(db, owner, "정산크루")
    moms = []
    for i in range(2):
        m = verified_user(f"부모{i}")
        inv = svc.create_invite(db, crew.id, owner)
        svc.join_crew(db, m, inv.token)
        moms.append(m)
    for u in [owner, *moms]:
        svc.submit_consent(db, crew.id, u, liability_ack=True, photo_consent=True, guardian_consent=True)
    svc.confirm_charter(db, crew.id, owner, settlement_mode="credit", credit_price_krw=10000)
    svc.activate_crew(db, crew.id, owner)
    return crew, owner, moms


def _run_session(db, crew, caregiver, guardians, date, start=15, end=17):
    """가능시간+빈칸 → 후보 → 전 가정 확정 → 장부 기입까지 한 세션을 돌린다."""
    board.add_slot(db, crew.id, caregiver, kind=SlotKind.AVAILABLE, date=date, start_hour=start, end_hour=end)
    for g in guardians:
        child = Child(guardian_id=g.id, name="아이", birth_year_month="2022-05", emergency_contact="010")
        db.add(child)
        db.flush()
        board.add_slot(db, crew.id, g, kind=SlotKind.NEED, date=date, start_hour=start, end_hour=end, child_id=child.id)
    [prop] = board.propose_assignments(db, crew.id, caregiver, date)
    session = None
    for g in guardians:
        session = board.confirm_assignment(db, prop.id, g) or session
    ledger.record_session_credits(db, session)
    return session


def test_settlement_confirm_offsets_ledger(db, credit_crew):
    """"받았어요" 확정 → 정산된 몫이 장부에서 상쇄돼 잔액이 0으로. 제로섬 유지."""
    crew, owner, (mom_b, mom_c) = credit_crew
    _run_session(db, crew, owner, [mom_b, mom_c], "2026-08-03")  # 아이2×2h → 오너 +4, 각 -2

    rows = ledger.compute_settlement(db, crew.id, "2026-08", owner)
    assert len(rows) == 2
    assert all(r.to_user == owner.id and r.amount_krw == 20000 for r in rows)

    for r in rows:
        ledger.confirm_settlement(db, r.id, owner)

    bal = ledger.balances(db, crew.id, owner)
    assert all(v == 0 for v in bal.values()), f"확정 후 잔액이 남음: {bal}"
    assert sum(bal.values()) == 0  # 상쇄 쌍도 제로섬


def test_confirmed_month_not_recharged(db, credit_crew):
    """§22 핵심 시나리오: 8월 정산 확정 → 9월 세션 → 9월 정산에 8월 몫 미포함."""
    crew, owner, (mom_b, mom_c) = credit_crew
    _run_session(db, crew, owner, [mom_b, mom_c], "2026-08-03")  # 오너 +4, B -2, C -2

    aug = ledger.compute_settlement(db, crew.id, "2026-08", owner)
    for r in aug:
        ledger.confirm_settlement(db, r.id, owner)

    # 9월: B의 아이 하나만 3시간 (14~17시) → B -3, 오너 +3
    _run_session(db, crew, owner, [mom_b], "2026-09-07", start=14, end=17)

    sep = ledger.compute_settlement(db, crew.id, "2026-09", owner)
    assert len(sep) == 1, f"9월 정산에 8월 몫이 섞임: {[(s.from_user, s.amount_krw) for s in sep]}"
    assert sep[0].from_user == mom_b.id and sep[0].to_user == owner.id
    assert sep[0].amount_krw == 30000  # 9월 몫(3크레딧)만. 8월 2크레딧이 더해지면 50000
    assert not any(s.from_user == mom_c.id for s in sep)  # C는 8월에 정산 끝


def test_pending_settlement_not_double_proposed(db, credit_crew):
    """8월 정산이 미확정(PENDING)이어도 9월 계산에 같은 몫을 다시 제안하지 않는다 (§22-3)."""
    crew, owner, (mom_b, mom_c) = credit_crew
    _run_session(db, crew, owner, [mom_b, mom_c], "2026-08-03")

    aug = ledger.compute_settlement(db, crew.id, "2026-08", owner)
    assert len(aug) == 2  # 확정하지 않고 둔다 — 독촉·배지의 몫

    _run_session(db, crew, owner, [mom_b], "2026-09-07", start=14, end=17)

    sep = ledger.compute_settlement(db, crew.id, "2026-09", owner)
    assert len(sep) == 1
    assert sep[0].from_user == mom_b.id and sep[0].amount_krw == 30000
