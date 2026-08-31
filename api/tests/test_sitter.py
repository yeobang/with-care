"""P10 시터 트랙 (§25): 공구→분할 견적→가정별 확정(I4)→세션, 할증, 접근 경계, I3, 폴백, 상시성."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_db
from app.domain.models import Base
from app.domain.sitter_service import _today_kst
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


def _signup(client, name: str) -> str:
    uid = client.post("/users", json={"name": name}).json()["id"]
    client.post("/identity/verify", headers=_h(uid))
    return uid


def _consent(client, crew_id, uid):
    client.post(
        f"/crews/{crew_id}/consent",
        json={"liability_ack": True, "photo_consent": True, "guardian_consent": True},
        headers=_h(uid),
    )


def _child(client, uid, birth="2022-05") -> str:
    return client.post(
        "/my/children",
        json={"name": "아이", "birth_year_month": birth, "emergency_contact": "010"},
        headers=_h(uid),
    ).json()["id"]


@pytest.fixture
def setup(ctx):
    client, _ = ctx
    owner, mom, sitter = _signup(client, "오너"), _signup(client, "부모"), _signup(client, "시터")
    for uid in (owner, mom, sitter):
        client.post("/push/tokens", json={"token": _tok(uid)}, headers=_h(uid))
    crew_id = client.post("/crews", json={"name": "시터크루"}, headers=_h(owner)).json()["id"]
    t = client.post(f"/crews/{crew_id}/invites", headers=_h(owner)).json()["token"]
    client.post(f"/invites/{t}/join", headers=_h(mom))
    # 시터 전용 초대 (§25-1)
    t2 = client.post(f"/crews/{crew_id}/invites", json={"role": "sitter"}, headers=_h(owner)).json()["token"]
    client.post(f"/invites/{t2}/join", headers=_h(sitter))
    for uid in (owner, mom, sitter):
        _consent(client, crew_id, uid)
    client.post(f"/crews/{crew_id}/charter/confirm", json={}, headers=_h(owner))
    client.post(f"/crews/{crew_id}/activate", headers=_h(owner))
    kids = {owner: _child(client, owner), mom: _child(client, mom)}
    client.post("/sitters/me", json={"hourly_krw": 10000}, headers=_h(sitter))
    return {"client": client, "crew_id": crew_id, "owner": owner, "mom": mom, "sitter": sitter, "kids": kids}


def _make_request(s, date="2026-09-10", start=14, end=17):
    client = s["client"]
    req = client.post(
        f"/crews/{s['crew_id']}/sitter-requests",
        json={"date": date, "start_hour": start, "end_hour": end, "child_ids": [s["kids"][s["owner"]]]},
        headers=_h(s["owner"]),
    ).json()
    client.post(f"/sitter-requests/{req['id']}/join", json={"child_id": s["kids"][s["mom"]]}, headers=_h(s["mom"]))
    return req


def test_full_flow_quote_split_confirm_session(setup, sent):
    s, client = setup, setup["client"]
    req = _make_request(s)  # 3시간, 2가정
    sent.clear()
    quote = client.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(s["sitter"])).json()
    assert quote["total_krw"] == 30000 and quote["per_family_krw"] == 15000 and quote["surge"] is False
    assert {m["to"] for m in sent} == {_tok(s["owner"]), _tok(s["mom"])}  # 견적은 가정들에게

    # I4: 한 가정 확정만으로는 세션 없음
    assert client.post(f"/sitter-quotes/{quote['id']}/confirm", headers=_h(s["owner"])).json()["session_id"] is None
    sid = client.post(f"/sitter-quotes/{quote['id']}/confirm", headers=_h(s["mom"])).json()["session_id"]
    assert sid

    [req_after] = client.get(f"/crews/{s['crew_id']}/sitter-requests", headers=_h(s["owner"])).json()
    assert req_after["status"] == "matched"

    # 시터 세션은 크레딧 장부 무관 (§25-4): 인계 종료 후에도 장부 비어 있음
    client.post(f"/sessions/{sid}/handoff/start", headers=_h(s["owner"]))
    client.post(f"/sessions/{sid}/handoff/end", headers=_h(s["owner"]))
    assert client.get(f"/crews/{s['crew_id']}/ledger", headers=_h(s["owner"])).json() == {}

    # 재확정 탭 멱등
    again = client.post(f"/sitter-quotes/{quote['id']}/confirm", headers=_h(s["mom"])).json()
    assert again["session_id"] == sid


def test_same_day_surge_1_5x(setup):
    s, client = setup, setup["client"]
    req = _make_request(s, date=_today_kst())  # 당일 요청 (§17-A 긴급 할증)
    quote = client.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(s["sitter"])).json()
    assert quote["surge"] is True and quote["total_krw"] == 45000  # 30000 × 1.5


def test_sitter_access_boundaries(setup):
    """§25-2: 시터는 장부·보드 쓰기·초대 불가, 세션은 자기 것만."""
    s, client = setup, setup["client"]
    h = _h(s["sitter"])
    assert client.get(f"/crews/{s['crew_id']}/ledger", headers=h).status_code == 403
    assert client.post(
        f"/crews/{s['crew_id']}/slots",
        json={"kind": "available", "date": "2026-09-10", "start_hour": 14, "end_hour": 17},
        headers=h,
    ).status_code == 403
    assert client.get(f"/crews/{s['crew_id']}/board/gaps?date=2026-09-10", headers=h).status_code == 403
    assert client.post(f"/crews/{s['crew_id']}/invites", headers=h).status_code == 403
    assert client.get(f"/crews/{s['crew_id']}/sessions", headers=h).json() == []
    # 부모가 견적 제출 시도 → 시터 역할 아님
    req = _make_request(s)
    assert client.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(s["mom"])).status_code == 403


def test_quote_requires_profile(setup):
    s, client = setup, setup["client"]
    # 프로필 없는 두 번째 시터
    sitter2 = _signup(client, "시터2")
    t = client.post(f"/crews/{s['crew_id']}/invites", json={"role": "sitter"}, headers=_h(s["owner"])).json()["token"]
    client.post(f"/invites/{t}/join", headers=_h(sitter2))
    _consent(client, s["crew_id"], sitter2)
    req = _make_request(s)
    assert client.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(sitter2)).status_code == 422


def test_i3_blocked_at_sitter_session(setup):
    """I3: 시터 1인 + 타인 영유아 5인 세션 성립 불가 — 마지막 확정 탭에서 차단."""
    s, client = setup, setup["client"]
    extra = [_child(client, s["mom"]) for _ in range(4)]  # mom 아이 총 5
    req = client.post(
        f"/crews/{s['crew_id']}/sitter-requests",
        json={"date": "2026-09-11", "start_hour": 14, "end_hour": 16,
              "child_ids": [s["kids"][s["mom"]], *extra]},
        headers=_h(s["mom"]),
    ).json()
    quote = client.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(s["sitter"])).json()
    res = client.post(f"/sitter-quotes/{quote['id']}/confirm", headers=_h(s["mom"]))
    assert res.status_code == 403 and res.json()["invariant"] == "I3"


def test_sitter_cancel_reopens_request(setup, sent):
    """§25-5: 시터 세션 취소 → 크루 전체 알림 + 공구 재가동."""
    s, client = setup, setup["client"]
    req = _make_request(s)
    quote = client.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(s["sitter"])).json()
    client.post(f"/sitter-quotes/{quote['id']}/confirm", headers=_h(s["owner"]))
    sid = client.post(f"/sitter-quotes/{quote['id']}/confirm", headers=_h(s["mom"])).json()["session_id"]
    sent.clear()
    assert client.post(f"/sessions/{sid}/cancel", headers=_h(s["owner"])).status_code == 200
    [req_after] = client.get(f"/crews/{s['crew_id']}/sitter-requests", headers=_h(s["owner"])).json()
    assert req_after["status"] == "open"
    assert req_after["quotes"][0]["status"] == "declined"
    titles = {m["title"] for m in sent}
    assert "시터 돌봄 취소" in titles


def test_recurrence_warning_same_week(setup, sent):
    """§25-6: 같은 크루·시터, 같은 주 2회째 세션 성립 → 상시성 경고 (차단 아님)."""
    s, client = setup, setup["client"]
    for date in ("2026-09-07", "2026-09-09"):  # 같은 ISO 주
        req = client.post(
            f"/crews/{s['crew_id']}/sitter-requests",
            json={"date": date, "start_hour": 14, "end_hour": 16, "child_ids": [s["kids"][s["owner"]]]},
            headers=_h(s["owner"]),
        ).json()
        quote = client.post(f"/sitter-requests/{req['id']}/quotes", headers=_h(s["sitter"])).json()
        sent.clear()
        res = client.post(f"/sitter-quotes/{quote['id']}/confirm", headers=_h(s["owner"])).json()
        assert res["session_id"]  # 경고일 뿐 차단 아님
    titles = {m["title"] for m in sent}
    assert "상시성 주의" in titles


def test_join_only_own_child(setup):
    s, client = setup, setup["client"]
    req = _make_request(s)
    # mom이 owner의 아이로 참여 시도
    res = client.post(
        f"/sitter-requests/{req['id']}/join",
        json={"child_id": s["kids"][s["owner"]]}, headers=_h(s["mom"]),
    )
    assert res.status_code == 422
