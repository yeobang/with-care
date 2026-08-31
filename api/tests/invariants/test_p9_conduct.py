"""P9 규약 집행: 세션 취소·노쇼 기록·배지 (§24-1) + 호스트 사례 정산 (§24-2) + 교대 균형 (§24-3)."""

import pytest

from app.domain import board_service as board
from app.domain import crew_service as svc
from app.domain import errors
from app.domain import incident_service as inc
from app.domain import ledger_service as ledger
from app.domain.models import Child, IncidentKind, PushToken, SlotKind, _now


@pytest.fixture
def crew3(db, verified_user):
    def _make(settlement_mode="credit", host_fee=5000):
        owner = verified_user("오너")
        crew = svc.create_crew(db, owner, "P9크루")
        moms, kids = [], {}
        for i in range(2):
            m = verified_user(f"부모{i}")
            svc.join_crew(db, m, svc.create_invite(db, crew.id, owner).token)
            moms.append(m)
        for u in [owner, *moms]:
            svc.submit_consent(db, crew.id, u, liability_ack=True, photo_consent=True, guardian_consent=True)
        svc.confirm_charter(
            db, crew.id, owner,
            settlement_mode=settlement_mode, credit_price_krw=10000,
            host_fee_krw=host_fee, no_show_fine_krw=10000,
        )
        svc.activate_crew(db, crew.id, owner)
        for m in moms:
            child = Child(guardian_id=m.id, name="아이", birth_year_month="2022-05", emergency_contact="010")
            db.add(child)
            db.flush()
            kids[m.id] = child
        return crew, owner, moms, kids

    return _make


def _session(db, crew, owner, moms, kids, date="2026-09-07", only_first=False):
    board.add_slot(db, crew.id, owner, kind=SlotKind.AVAILABLE, date=date, start_hour=15, end_hour=17)
    targets = moms[:1] if only_first else moms
    for m in targets:
        board.add_slot(db, crew.id, m, kind=SlotKind.NEED, date=date, start_hour=15, end_hour=17, child_id=kids[m.id].id)
    [p] = board.propose_assignments(db, crew.id, owner, date)
    session = None
    for m in targets:
        session = board.confirm_assignment(db, p.id, m) or session
    return session


# --- 취소 ---


def test_cancel_blocks_ledger(db, crew3):
    crew, owner, moms, kids = crew3()
    s = _session(db, crew, owner, moms, kids)
    inc.cancel_session(db, s.id, moms[0])
    ledger.record_session_credits(db, s)  # 취소된 세션 → 기입 없음
    assert ledger.balances(db, crew.id, owner) == {}


def test_cancel_after_start_blocked(db, crew3):
    """시작된 세션은 취소 불가 — 기록 무결성 (§4-A). 문제는 인시던트로."""
    crew, owner, moms, kids = crew3()
    s = _session(db, crew, owner, moms, kids)
    s.handoff_started_at = _now()
    db.flush()
    with pytest.raises(ValueError):
        inc.cancel_session(db, s.id, moms[0])


def test_cancel_only_by_participant(db, crew3):
    crew, owner, moms, kids = crew3()
    s = _session(db, crew, owner, moms, kids, only_first=True)  # mom[1]은 세션 밖
    with pytest.raises(errors.HumanChoiceViolation):
        inc.cancel_session(db, s.id, moms[1])


# --- 노쇼 기록·배지 ---


def test_incident_fine_snapshot_and_idempotent(db, crew3):
    crew, owner, moms, kids = crew3()
    s = _session(db, crew, owner, moms, kids)
    incident, created = inc.report_incident(
        db, s.id, moms[0], kind=IncidentKind.NO_SHOW, offender_id=owner.id
    )
    assert created and incident.fine_krw == 10000  # 기록 시점 규약 스냅샷
    again, created2 = inc.report_incident(
        db, s.id, moms[0], kind=IncidentKind.NO_SHOW, offender_id=owner.id
    )
    assert not created2 and again.id == incident.id  # 중복 기록 멱등
    [badge] = inc.incident_counts(db, crew.id, owner)
    assert badge["user_id"] == owner.id and badge["count"] == 1


def test_incident_offender_must_be_participant(db, crew3):
    crew, owner, moms, kids = crew3()
    s = _session(db, crew, owner, moms, kids, only_first=True)
    with pytest.raises(ValueError):
        inc.report_incident(db, s.id, moms[0], kind=IncidentKind.NO_SHOW, offender_id=moms[1].id)
    with pytest.raises(errors.HumanChoiceViolation):
        inc.report_incident(db, s.id, moms[1], kind=IncidentKind.NO_SHOW, offender_id=owner.id)


# --- 호스트 사례 (§24-2) ---


def test_host_fee_added_to_settlement(db, crew3):
    crew, owner, moms, kids = crew3(host_fee=5000)
    s = _session(db, crew, owner, moms, kids)
    s.handoff_ended_at = _now()
    db.flush()
    ledger.record_session_credits(db, s)

    rows = ledger.compute_settlement(db, crew.id, "2026-09", owner)
    credit_rows = [r for r in rows if r.amount_credits > 0]
    host_rows = [r for r in rows if r.amount_credits == 0]
    assert len(credit_rows) == 2 and all(r.amount_krw == 20000 for r in credit_rows)
    # 사례 5000 ÷ 2가정 = 2500씩, 돌봄자에게
    assert len(host_rows) == 2
    assert all(r.amount_krw == 2500 and r.to_user == owner.id for r in host_rows)


def test_host_fee_confirm_does_not_touch_ledger(db, crew3):
    crew, owner, moms, kids = crew3(host_fee=5000)
    s = _session(db, crew, owner, moms, kids)
    s.handoff_ended_at = _now()
    db.flush()
    ledger.record_session_credits(db, s)
    rows = ledger.compute_settlement(db, crew.id, "2026-09", owner)
    before = ledger.balances(db, crew.id, owner)
    host_row = next(r for r in rows if r.amount_credits == 0)
    ledger.confirm_settlement(db, host_row.id, owner)
    assert ledger.balances(db, crew.id, owner) == before  # 원화 전용 — 장부 무변화


def test_canceled_session_no_host_fee(db, crew3):
    crew, owner, moms, kids = crew3(host_fee=5000)
    s = _session(db, crew, owner, moms, kids)
    inc.cancel_session(db, s.id, owner)
    rows = ledger.compute_settlement(db, crew.id, "2026-09", owner)
    assert rows == []  # 장부도 사례도 없음


# --- 교대 균형 (§24-3) ---


def _register_tokens(db, users):
    for u in users:
        db.add(PushToken(user_id=u.id, token=f"ExponentPushToken[{u.id}]"))
    db.flush()


def test_rotation_balance_notified_over_threshold(db, crew3, monkeypatch):
    from app import notifications

    crew, owner, moms, kids = crew3(settlement_mode="rotation")
    _register_tokens(db, [owner, *moms])
    s = _session(db, crew, owner, moms, kids)  # 오너 +4 → 편차 6? (최대4 − 최소−2 = 6 ≥ 4)
    s.handoff_ended_at = _now()
    db.flush()
    ledger.record_session_credits(db, s)

    sent = []
    monkeypatch.setattr(
        "app.infra.push.send", lambda msgs: (sent.extend(msgs), [{"status": "ok"} for _ in msgs])[1]
    )
    notifications.notify_rotation_balance(db)
    assert {m["to"] for m in sent} == {f"ExponentPushToken[{u.id}]" for u in [owner, *moms]}


def test_rotation_balance_quiet_under_threshold(db, crew3, monkeypatch):
    from app import notifications

    crew, owner, moms, kids = crew3(settlement_mode="rotation")
    _register_tokens(db, [owner, *moms])
    # 1아이×1시간 세션 → 편차 1−(−1)=2 < 4
    board.add_slot(db, crew.id, owner, kind=SlotKind.AVAILABLE, date="2026-09-08", start_hour=15, end_hour=16)
    board.add_slot(db, crew.id, moms[0], kind=SlotKind.NEED, date="2026-09-08", start_hour=15, end_hour=16, child_id=kids[moms[0].id].id)
    [p] = board.propose_assignments(db, crew.id, owner, "2026-09-08")
    s = board.confirm_assignment(db, p.id, moms[0])
    ledger.record_session_credits(db, s)

    sent = []
    monkeypatch.setattr(
        "app.infra.push.send", lambda msgs: (sent.extend(msgs), [{"status": "ok"} for _ in msgs])[1]
    )
    notifications.notify_rotation_balance(db)
    assert sent == []


def test_credit_mode_crew_not_rotation_notified(db, crew3, monkeypatch):
    from app import notifications

    crew, owner, moms, kids = crew3(settlement_mode="credit")
    _register_tokens(db, [owner, *moms])
    s = _session(db, crew, owner, moms, kids)
    ledger.record_session_credits(db, s)

    sent = []
    monkeypatch.setattr(
        "app.infra.push.send", lambda msgs: (sent.extend(msgs), [{"status": "ok"} for _ in msgs])[1]
    )
    notifications.notify_rotation_balance(db)
    assert sent == []  # rotation 전용 알림
