"""P7 푸시: 이벤트 알림·독촉 — 수신자 한정(I6)·재탭 무알림·발송 실패 격리까지."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_db
from app.domain.models import Base, PushToken
from app.main import app


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        db = TestSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app), TestSession
    app.dependency_overrides.clear()


@pytest.fixture
def sent(monkeypatch):
    box: list[dict] = []

    def fake_send(messages):
        box.extend(messages)
        return [{"status": "ok"} for _ in messages]

    monkeypatch.setattr("app.infra.push.send", fake_send)
    return box


def _h(uid: str) -> dict:
    return {"X-User-Id": uid}


def _tok(uid: str) -> str:
    return f"ExponentPushToken[{uid}]"


@pytest.fixture
def crew(ctx):
    """활성 크루(오너+부모2, credit 단가 10000) + 아이 + 전원 푸시 토큰 등록."""
    client, _ = ctx
    users = []
    for i in range(3):
        uid = client.post("/users", json={"name": f"P{i}"}).json()["id"]
        client.post("/identity/verify", headers=_h(uid))
        client.post("/push/tokens", json={"token": _tok(uid)}, headers=_h(uid))
        users.append(uid)
    owner, mom_b, mom_c = users
    crew_id = client.post("/crews", json={"name": "푸시크루"}, headers=_h(owner)).json()["id"]
    for uid in (mom_b, mom_c):
        t = client.post(f"/crews/{crew_id}/invites", headers=_h(owner)).json()["token"]
        client.post(f"/invites/{t}/join", headers=_h(uid))
    for uid in users:
        client.post(
            f"/crews/{crew_id}/consent",
            json={"liability_ack": True, "photo_consent": True, "guardian_consent": True},
            headers=_h(uid),
        )
    client.post(
        f"/crews/{crew_id}/charter/confirm",
        json={"settlement_mode": "credit", "credit_price_krw": 10000},
        headers=_h(owner),
    )
    client.post(f"/crews/{crew_id}/activate", headers=_h(owner))
    kids = {}
    for uid in (mom_b, mom_c):
        kids[uid] = client.post(
            "/my/children",
            json={"name": "아이", "birth_year_month": "2022-05", "emergency_contact": "010"},
            headers=_h(uid),
        ).json()["id"]
    return {"client": client, "crew_id": crew_id, "owner": owner, "moms": [mom_b, mom_c], "kids": kids}


def _board(c, date="2026-09-07"):
    client = c["client"]
    client.post(
        f"/crews/{c['crew_id']}/slots",
        json={"kind": "available", "date": date, "start_hour": 15, "end_hour": 17},
        headers=_h(c["owner"]),
    )
    for m in c["moms"]:
        client.post(
            f"/crews/{c['crew_id']}/slots",
            json={"kind": "need", "date": date, "start_hour": 15, "end_hour": 17, "child_id": c["kids"][m]},
            headers=_h(m),
        )
    [p] = client.post(f"/crews/{c['crew_id']}/propose?date={date}", headers=_h(c["owner"])).json()
    return p


def test_propose_notifies_need_guardians_only(crew, sent):
    _board(crew)
    tos = [m["to"] for m in sent]
    assert _tok(crew["moms"][0]) in tos and _tok(crew["moms"][1]) in tos
    assert _tok(crew["owner"]) not in tos  # 돌봄자는 후보 단계 알림 대상 아님


def test_confirm_notifies_once_and_not_on_retap(crew, sent):
    p = _board(crew)
    client = crew["client"]
    client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][0]))
    sent.clear()
    client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][1]))
    tos = [m["to"] for m in sent]
    assert _tok(crew["owner"]) in tos  # 세션 확정은 돌봄자 포함 전원
    n = len(sent)
    client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][1]))  # 재탭 멱등
    assert len(sent) == n  # 재탭은 무알림


def test_photo_push_excludes_uploader(crew, sent, monkeypatch):
    monkeypatch.setattr("app.infra.storage.upload", lambda *a, **k: None)
    p = _board(crew)
    client = crew["client"]
    client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][0]))
    sid = client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][1])).json()["session_id"]
    sent.clear()
    client.post(
        f"/sessions/{sid}/photos",
        files={"file": ("a.jpg", b"x", "image/jpeg")},
        headers=_h(crew["owner"]),
    )
    assert {m["to"] for m in sent} == {_tok(crew["moms"][0]), _tok(crew["moms"][1])}


def test_nudge_targets_debtors(crew, sent):
    p = _board(crew)
    client = crew["client"]
    client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][0]))
    sid = client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][1])).json()["session_id"]
    client.post(f"/sessions/{sid}/handoff/start", headers=_h(crew["owner"]))
    client.post(f"/sessions/{sid}/handoff/end", headers=_h(crew["owner"]))
    client.post(f"/crews/{crew['crew_id']}/settlements/2026-09/compute", headers=_h(crew["owner"]))
    sent.clear()
    res = client.post(f"/crews/{crew['crew_id']}/settlements/nudge", headers=_h(crew["owner"])).json()
    assert res["nudged_users"] == 2
    assert {m["to"] for m in sent} == {_tok(crew["moms"][0]), _tok(crew["moms"][1])}


def test_push_failure_does_not_break_flow(crew, monkeypatch):
    def boom(messages):
        raise RuntimeError("expo down")

    monkeypatch.setattr("app.infra.push.send", boom)
    p = _board(crew)  # propose 내부 발송 실패 → 무시돼야 함
    assert p["status"] == "proposed"


def test_dead_tokens_cleaned(ctx, crew, monkeypatch):
    _, TestSession = ctx
    monkeypatch.setattr(
        "app.infra.push.send",
        lambda msgs: [{"status": "error", "details": {"error": "DeviceNotRegistered"}} for _ in msgs],
    )
    _board(crew)
    with TestSession() as db:
        remaining = {t.token for t in db.scalars(select(PushToken)).all()}
    assert _tok(crew["moms"][0]) not in remaining and _tok(crew["moms"][1]) not in remaining
    assert _tok(crew["owner"]) in remaining  # 발송된 적 없는 토큰은 유지


def test_gap_rerequest_pushes_to_others(crew, sent):
    """빈칸 재요청은 요청자 제외 크루 전원에게 (P8)."""
    client = crew["client"]
    m = crew["moms"][0]
    client.post(
        f"/crews/{crew['crew_id']}/slots",
        json={"kind": "need", "date": "2026-09-08", "start_hour": 15, "end_hour": 17, "child_id": crew["kids"][m]},
        headers=_h(m),
    )
    sent.clear()
    res = client.post(f"/crews/{crew['crew_id']}/board/rerequest?date=2026-09-08", headers=_h(m)).json()
    assert res["gaps"] == 1
    assert {x["to"] for x in sent} == {_tok(crew["owner"]), _tok(crew["moms"][1])}


def test_decline_notifies_others_once(crew, sent):
    p = _board(crew)
    client = crew["client"]
    sent.clear()
    client.post(f"/assignments/{p['id']}/decline", headers=_h(crew["moms"][0]))
    assert {x["to"] for x in sent} == {_tok(crew["owner"]), _tok(crew["moms"][1])}
    n = len(sent)
    client.post(f"/assignments/{p['id']}/decline", headers=_h(crew["moms"][0]))  # 재탭
    assert len(sent) == n


def test_cancel_notifies_others_and_blocks_handoff(crew, sent):
    """취소 알림(취소자 제외) + 취소된 세션 인계 차단 (P9)."""
    p = _board(crew)
    client = crew["client"]
    client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][0]))
    sid = client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][1])).json()["session_id"]
    sent.clear()
    assert client.post(f"/sessions/{sid}/cancel", headers=_h(crew["moms"][0])).status_code == 200
    assert {x["to"] for x in sent} == {_tok(crew["owner"]), _tok(crew["moms"][1])}
    n = len(sent)
    client.post(f"/sessions/{sid}/cancel", headers=_h(crew["moms"][0]))  # 재탭 무알림
    assert len(sent) == n
    assert client.post(f"/sessions/{sid}/handoff/start", headers=_h(crew["owner"])).status_code == 422


def test_incident_fine_notice_to_offender_once(crew, sent):
    """노쇼 기록 → 당사자에게 벌금 고지 1회. 중복 기록은 무알림 (§24-1)."""
    p = _board(crew)
    client = crew["client"]
    client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][0]))
    sid = client.post(f"/assignments/{p['id']}/confirm", headers=_h(crew["moms"][1])).json()["session_id"]
    sent.clear()
    body = {"kind": "no_show", "offender_id": crew["owner"]}
    res = client.post(f"/sessions/{sid}/incidents", json=body, headers=_h(crew["moms"][0])).json()
    assert res["fine_krw"] == 10000
    assert [x["to"] for x in sent] == [_tok(crew["owner"])]
    client.post(f"/sessions/{sid}/incidents", json=body, headers=_h(crew["moms"][1]))  # 중복
    assert len(sent) == 1
    [badge] = client.get(f"/crews/{crew['crew_id']}/incidents", headers=_h(crew["owner"])).json()
    assert badge["count"] == 1 and badge["user_id"] == crew["owner"]


def test_register_token_upsert(ctx):
    client, TestSession = ctx
    u1 = client.post("/users", json={"name": "a"}).json()["id"]
    u2 = client.post("/users", json={"name": "b"}).json()["id"]
    for uid in (u1, u2):
        client.post("/push/tokens", json={"token": "ExponentPushToken[shared-device]"}, headers=_h(uid))
    with TestSession() as db:
        rows = db.scalars(
            select(PushToken).where(PushToken.token == "ExponentPushToken[shared-device]")
        ).all()
    assert len(rows) == 1 and rows[0].user_id == u2  # 기기 주인 이관
