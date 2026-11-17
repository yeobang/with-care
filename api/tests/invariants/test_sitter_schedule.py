"""S1-2: 일정 단위 명시적 확정과 회차의 안전 경계."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select, func

from tests.test_sitter import ctx, setup, sent, _h, _child, _signup, _join, _consent
from app.domain.models import CareSession, SitterQuote, SitterQuoteFamily
from app.domain.sitter_service import _today_kst


def propose(s, weekdays=None, children=None):
    day = date.fromisoformat(_today_kst()) + timedelta(days=7)
    r = s["client"].post(
        f"/crews/{s['crew_id']}/sitter-requests",
        json={"date": day.isoformat(), "start_hour": 15, "end_hour": 18,
              "weekdays": [0, 2, 4] if weekdays is None else weekdays,
              "child_ids": children or [s["kids"][s["owner"]]]},
        headers=_h(s["owner"]),
    )
    assert r.status_code == 200, r.text
    req = r.json()
    assert s["client"].post(f"/sitter-requests/{req['id']}/join",
        json={"child_id": s["kids"][s["mom"]]}, headers=_h(s["mom"])).status_code == 200
    return req


def quote(s, req):
    r = s["client"].post(f"/sitter-requests/{req['id']}/quotes", headers=_h(s["sitter"]))
    assert r.status_code == 200, r.text
    return r.json()


def confirm(s, q, who, **kwargs):
    return s["client"].post(f"/sitter-quotes/{q['id']}/confirm", headers=_h(who), **kwargs)


def count(ctx):
    with ctx[1]() as db:
        return db.scalar(select(func.count()).select_from(CareSession))


def test_partial_confirmation_and_impersonation_create_no_sessions(setup, ctx):
    s = setup
    req = propose(s)
    q = quote(s, req)
    assert count(ctx) == 0
    # 요청 본문으로 다른 가정을 지정해도 인증된 자기 가정만 확정된다.
    for _ in range(2):
        r = confirm(s, q, s["owner"], json={"guardian_id": s["mom"]})
        assert r.status_code == 200 and r.json()["session_ids"] == []
    assert count(ctx) == 0
    with ctx[1]() as db:
        families = db.scalars(select(SitterQuoteFamily).where(SitterQuoteFamily.quote_id == q["id"])).all()
        assert {f.guardian_id: f.confirmed for f in families} == {s["owner"]: True, s["mom"]: False}
    stranger = _signup(s["client"], "비참여 가정")
    _join(s["client"], s["crew_id"], s["owner"], stranger)
    _consent(s["client"], s["crew_id"], stranger)
    r = confirm(s, q, stranger)
    assert r.status_code == 403 and r.json()["invariant"] == "I4"
    assert count(ctx) == 0


def test_all_confirm_dates_split_snapshot_idempotency_warning_and_cancel(setup, ctx, sent):
    s, c = setup, setup["client"]
    second = _child(c, s["owner"])
    c.post("/sitters/me", json={"hourly_krw": 10000, "shared_hourly_krw": 14000}, headers=_h(s["sitter"]))
    req = propose(s, children=[s["kids"][s["owner"]], second])
    q = quote(s, req)
    c.post("/sitters/me", json={"hourly_krw": 99000}, headers=_h(s["sitter"]))
    confirm(s, q, s["owner"])
    sent.clear()
    r = confirm(s, q, s["mom"])
    assert r.status_code == 200, r.text
    ids = r.json()["session_ids"]
    assert len(ids) == 12 and count(ctx) == 12
    assert "상시성 주의" in {m["title"] for m in sent}
    with ctx[1]() as db:
        sessions = db.scalars(select(CareSession).order_by(CareSession.date)).all()
        assert [x.date for x in sessions] == req["occurrence_dates"]
        for session in sessions:
            assert (session.start_hour, session.end_hour) == (15, 18)
            oq = db.get(SitterQuote, session.sitter_quote_id)
            assert (oq.hourly_krw, oq.total_krw, oq.surge) == (14000, 42000, False)
            fams = db.scalars(select(SitterQuoteFamily).where(SitterQuoteFamily.quote_id == oq.id)).all()
            assert {f.guardian_id: f.amount_krw for f in fams} == {s["owner"]: 28000, s["mom"]: 14000}
    sent.clear()
    assert confirm(s, q, s["mom"]).json()["session_ids"] == ids
    assert sent == [] and count(ctx) == 12
    assert c.post(f"/sessions/{ids[0]}/cancel", headers=_h(s["owner"])).status_code == 200
    assert confirm(s, q, s["owner"]).json()["session_ids"] == ids
    with ctx[1]() as db:
        assert db.scalar(select(func.count()).select_from(CareSession).where(CareSession.canceled_at.is_not(None))) == 1


def test_join_after_quote_cannot_change_approved_terms(setup, ctx):
    s = setup
    req = propose(s)
    q = quote(s, req)
    confirm(s, q, s["owner"])
    extra = _child(s["client"], s["mom"])
    r = s["client"].post(f"/sitter-requests/{req['id']}/join",
        json={"child_id": extra}, headers=_h(s["mom"]))
    assert r.status_code == 403 and r.json()["invariant"] == "I4"
    assert count(ctx) == 0


def test_outsider_cannot_read_or_confirm(setup, ctx):
    s = setup
    req = propose(s)
    q = quote(s, req)
    outsider = _signup(s["client"], "외부")
    assert s["client"].get(f"/crews/{s['crew_id']}/sitter-requests", headers=_h(outsider)).status_code == 403
    assert confirm(s, q, outsider).status_code == 403
    assert count(ctx) == 0


def test_i3_rolls_back_entire_schedule(setup, ctx):
    s = setup
    # 실제 날짜에 무관하게 영유아인 아이 5명
    birth = (date.fromisoformat(_today_kst()).replace(day=1) - timedelta(days=365 * 4)).strftime("%Y-%m")
    kids = [_child(s["client"], s["owner"], birth=birth) for _ in range(5)]
    q = quote(s, propose(s, children=kids))
    confirm(s, q, s["owner"])
    r = confirm(s, q, s["mom"])
    assert r.status_code == 403 and r.json()["invariant"] == "I3"
    assert count(ctx) == 0


@pytest.mark.parametrize("weekdays", [[], [-1], [7]])
def test_invalid_weekdays(setup, weekdays):
    s = setup
    r = s["client"].post(f"/crews/{s['crew_id']}/sitter-requests",
        json={"date": "2099-01-01", "start_hour": 15, "end_hour": 18,
              "weekdays": weekdays, "child_ids": [s["kids"][s["owner"]]]}, headers=_h(s["owner"]))
    assert r.status_code == 422


def test_expired_schedule_cannot_confirm(setup, ctx, monkeypatch):
    s = setup
    req = propose(s)
    q = quote(s, req)
    monkeypatch.setattr("app.domain.sitter_service._today_kst", lambda: req["date"])
    assert confirm(s, q, s["owner"]).status_code == 422
    assert count(ctx) == 0


@pytest.mark.parametrize("gate", ["consent", "charter"])
def test_final_confirmation_rechecks_activity_gates(setup, ctx, gate):
    from app.domain.models import Consent, Crew, CrewStatus
    s = setup
    q = quote(s, propose(s))
    confirm(s, q, s["owner"])
    with ctx[1]() as db:
        if gate == "consent":
            consent = db.scalar(select(Consent).where(Consent.crew_id == s["crew_id"], Consent.user_id == s["owner"]))
            consent.consented_at = None
        else:
            db.get(Crew, s["crew_id"]).status = CrewStatus.DRAFT
        db.commit()
    r = confirm(s, q, s["mom"])
    assert r.status_code == 403
    assert r.json()["invariant"] == ("I2" if gate == "consent" else "I7")
    assert count(ctx) == 0


def test_other_candidate_cannot_create_second_series(setup, ctx):
    s, c = setup, setup["client"]
    req = propose(s)
    q = quote(s, req)
    sitter2 = _signup(c, "두 번째 시터")
    _join(c, s["crew_id"], s["owner"], sitter2, role="sitter")
    _consent(c, s["crew_id"], sitter2)
    c.post("/sitters/me", json={"hourly_krw": 11000}, headers=_h(sitter2))
    q2 = c.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(sitter2)).json()
    confirm(s, q2, s["owner"])
    confirm(s, q, s["owner"])
    assert confirm(s, q, s["mom"]).status_code == 200
    assert confirm(s, q2, s["mom"]).status_code == 422
    assert count(ctx) == 12


def test_declined_schedule_never_creates_sessions(setup, ctx):
    s = setup
    q = quote(s, propose(s))
    confirm(s, q, s["owner"])
    assert s["client"].post(f"/sitter-quotes/{q['id']}/decline", headers=_h(s["mom"])).status_code == 200
    assert confirm(s, q, s["mom"]).status_code == 422
    assert count(ctx) == 0
