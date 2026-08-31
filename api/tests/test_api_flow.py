"""HTTP 통합 테스트: 크루 1개의 한 주 흐름 완주 (P3 완료 기준의 서버측 절반).

가입 → 크루 생성 → 초대·합류 → 합의 → 규약 확정 → 활성화 →
아이 등록 → 보드 입력 → 후보 나열 → 가정별 확정 → 세션 → 인계 탭.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_db
from app.domain.models import Base
from app.main import app


@pytest.fixture
def client():
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
    yield TestClient(app)
    app.dependency_overrides.clear()


def _h(user_id: str) -> dict:
    return {"X-User-Id": user_id}


def _signup(client: TestClient, name: str) -> str:
    """가입 + 본인인증(스텁) — P6부터 가입만으로는 verified가 아니다."""
    uid = client.post("/users", json={"name": name}).json()["id"]
    assert client.post("/identity/verify", headers=_h(uid)).status_code == 200
    return uid


def test_full_week_flow(client):
    # 가입 (3가구)
    users = [client.post("/users", json={"name": f"가구{i}"}).json() for i in range(3)]
    for _u in users:
        assert client.post("/identity/verify", headers=_h(_u["id"])).status_code == 200
    owner, mom_b, mom_c = (u["id"] for u in users)

    # 크루 생성 → 초대 → 합류
    crew = client.post("/crews", json={"name": "우리동네크루"}, headers=_h(owner)).json()
    crew_id = crew["id"]
    for uid in (mom_b, mom_c):
        token = client.post(f"/crews/{crew_id}/invites", headers=_h(owner)).json()["token"]
        res = client.post(f"/invites/{token}/join", headers=_h(uid))
        assert res.status_code == 200

    # 활성화 시도 → 규약 미확정으로 차단 (I7이 HTTP까지 도달하는지)
    res = client.post(f"/crews/{crew_id}/activate", headers=_h(owner))
    assert res.status_code == 403 and res.json()["invariant"] == "I7"

    # 전원 합의 + 규약 확정(단가만 조정) + 활성화
    for uid in (owner, mom_b, mom_c):
        assert client.post(
            f"/crews/{crew_id}/consent",
            json={"liability_ack": True, "photo_consent": True, "guardian_consent": True},
            headers=_h(uid),
        ).status_code == 200
    assert client.post(
        f"/crews/{crew_id}/charter/confirm", json={"credit_price_krw": 7000}, headers=_h(owner)
    ).status_code == 200
    res = client.post(f"/crews/{crew_id}/activate", headers=_h(owner))
    assert res.status_code == 200 and res.json()["status"] == "active"

    # 아이 등록 (B·C 가구)
    kids = {}
    for uid in (mom_b, mom_c):
        kids[uid] = client.post(
            "/my/children",
            json={"name": "아이", "birth_year_month": "2022-05", "emergency_contact": "010-0000-0000"},
            headers=_h(uid),
        ).json()["id"]

    # 주간 보드: 오너는 가능, B·C는 필요
    date = "2026-09-07"
    assert client.post(
        f"/crews/{crew_id}/slots",
        json={"kind": "available", "date": date, "start_hour": 14, "end_hour": 18},
        headers=_h(owner),
    ).status_code == 200
    for uid in (mom_b, mom_c):
        assert client.post(
            f"/crews/{crew_id}/slots",
            json={"kind": "need", "date": date, "start_hour": 15, "end_hour": 17, "child_id": kids[uid]},
            headers=_h(uid),
        ).status_code == 200

    # 후보 나열 (효력 없음) → 가정별 확정 → 전원 확정 시 세션
    [proposal] = client.post(f"/crews/{crew_id}/propose?date={date}", headers=_h(owner)).json()
    assert proposal["status"] == "proposed"
    assert client.post(f"/assignments/{proposal['id']}/confirm", headers=_h(mom_b)).json()["session_id"] is None
    session_id = client.post(f"/assignments/{proposal['id']}/confirm", headers=_h(mom_c)).json()["session_id"]
    assert session_id

    # 인계 탭 → 기록 확인
    assert client.post(f"/sessions/{session_id}/handoff/start", headers=_h(mom_b)).status_code == 200
    assert client.post(f"/sessions/{session_id}/handoff/end", headers=_h(mom_b)).status_code == 200
    [session] = client.get(f"/crews/{crew_id}/sessions", headers=_h(owner)).json()
    assert session["handoff_started_at"] and session["handoff_ended_at"]

    # I6: 크루 밖 사용자는 아무것도 못 본다
    outsider = _signup(client, "외부인")
    res = client.get(f"/crews/{crew_id}/sessions", headers=_h(outsider))
    assert res.status_code == 403 and res.json()["invariant"] == "I6"


def test_session_photos_flow(client, monkeypatch):
    """사진 업로드/조회 + I6: 크루 밖 사용자 차단. 스토리지는 모킹."""
    uploaded = {}
    monkeypatch.setattr("app.infra.storage.upload", lambda path, content, ct: uploaded.update({path: content}))
    monkeypatch.setattr(
        "app.infra.storage.signed_urls",
        lambda paths: {p: f"https://signed.example/{p}" for p in paths},
    )

    # 최소 흐름으로 세션 하나 생성
    users = [_signup(client, f"u{i}") for i in range(2)]
    owner, mom = users
    crew_id = client.post("/crews", json={"name": "포토크루"}, headers=_h(owner)).json()["id"]
    token = client.post(f"/crews/{crew_id}/invites", headers=_h(owner)).json()["token"]
    client.post(f"/invites/{token}/join", headers=_h(mom))
    for uid in users:
        client.post(
            f"/crews/{crew_id}/consent",
            json={"liability_ack": True, "photo_consent": True, "guardian_consent": True},
            headers=_h(uid),
        )
    client.post(f"/crews/{crew_id}/charter/confirm", json={}, headers=_h(owner))
    client.post(f"/crews/{crew_id}/activate", headers=_h(owner))
    kid = client.post(
        "/my/children",
        json={"name": "아이", "birth_year_month": "2022-05", "emergency_contact": "010"},
        headers=_h(mom),
    ).json()["id"]
    date = "2026-09-07"
    client.post(f"/crews/{crew_id}/slots", json={"kind": "available", "date": date, "start_hour": 14, "end_hour": 18}, headers=_h(owner))
    client.post(f"/crews/{crew_id}/slots", json={"kind": "need", "date": date, "start_hour": 15, "end_hour": 17, "child_id": kid}, headers=_h(mom))
    [proposal] = client.post(f"/crews/{crew_id}/propose?date={date}", headers=_h(owner)).json()
    session_id = client.post(f"/assignments/{proposal['id']}/confirm", headers=_h(mom)).json()["session_id"]

    # 업로드 (돌봄자) → 조회 (맡긴 부모)
    res = client.post(
        f"/sessions/{session_id}/photos",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers=_h(owner),
    )
    assert res.status_code == 200
    photos = client.get(f"/sessions/{session_id}/photos", headers=_h(mom)).json()
    assert len(photos) == 1 and photos[0]["url"].startswith("https://signed.example/")
    assert len(uploaded) == 1

    # I6: 외부인은 업로드도 조회도 불가
    outsider = _signup(client, "외부인")
    assert client.get(f"/sessions/{session_id}/photos", headers=_h(outsider)).status_code == 403
    assert client.post(
        f"/sessions/{session_id}/photos",
        files={"file": ("x.jpg", b"z", "image/jpeg")},
        headers=_h(outsider),
    ).status_code == 403


def test_ledger_and_settlement_flow(client):
    """세션 종료 → 장부 기입(아이·시간 제로섬) → 월말 정산 계산 → 받았어요 확인."""
    users = [_signup(client, f"L{i}") for i in range(3)]
    owner, mom_b, mom_c = users
    crew_id = client.post("/crews", json={"name": "장부크루"}, headers=_h(owner)).json()["id"]
    for uid in (mom_b, mom_c):
        token = client.post(f"/crews/{crew_id}/invites", headers=_h(owner)).json()["token"]
        client.post(f"/invites/{token}/join", headers=_h(uid))
    for uid in users:
        client.post(
            f"/crews/{crew_id}/consent",
            json={"liability_ack": True, "photo_consent": True, "guardian_consent": True},
            headers=_h(uid),
        )
    # 정산 모드 credit + 단가 10000원
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
    date = "2026-08-03"  # 8월 세션
    client.post(f"/crews/{crew_id}/slots", json={"kind": "available", "date": date, "start_hour": 15, "end_hour": 17}, headers=_h(owner))
    for uid in (mom_b, mom_c):
        client.post(f"/crews/{crew_id}/slots", json={"kind": "need", "date": date, "start_hour": 15, "end_hour": 17, "child_id": kids[uid]}, headers=_h(uid))
    [proposal] = client.post(f"/crews/{crew_id}/propose?date={date}", headers=_h(owner)).json()
    client.post(f"/assignments/{proposal['id']}/confirm", headers=_h(mom_b))
    session_id = client.post(f"/assignments/{proposal['id']}/confirm", headers=_h(mom_c)).json()["session_id"]

    # 인계 종료 전에는 장부가 비어 있다
    assert client.get(f"/crews/{crew_id}/ledger", headers=_h(owner)).json() == {}
    client.post(f"/sessions/{session_id}/handoff/start", headers=_h(mom_b))
    client.post(f"/sessions/{session_id}/handoff/end", headers=_h(mom_b))

    # 아이·시간 제로섬: 오너 +4 (아이2×2h), B·C 각 -2
    bal = client.get(f"/crews/{crew_id}/ledger", headers=_h(owner)).json()
    assert bal[owner] == 4 and bal[mom_b] == -2 and bal[mom_c] == -2
    assert sum(bal.values()) == 0

    # 월말 정산: 크레딧 B→오너 20000, C→오너 20000 (2크레딧×10000)
    # + 호스트 사례 (§24-2): 규약 기본 5000 ÷ 2가정 = 2500씩 → 총 4건
    rows = client.post(f"/crews/{crew_id}/settlements/2026-08/compute", headers=_h(owner)).json()
    credit_rows = [r for r in rows if r["amount_credits"] > 0]
    host_rows = [r for r in rows if r["amount_credits"] == 0]
    assert len(credit_rows) == 2
    assert all(r["to_user"] == owner and r["amount_krw"] == 20000 for r in credit_rows)
    assert len(host_rows) == 2
    assert all(r["to_user"] == owner and r["amount_krw"] == 2500 for r in host_rows)
    # 멱등
    again = client.post(f"/crews/{crew_id}/settlements/2026-08/compute", headers=_h(owner)).json()
    assert len(again) == 4

    # "받았어요"는 받는 사람만 (보낸 사람이 누르면 403)
    target = credit_rows[0]
    assert client.post(f"/settlements/{target['id']}/received", headers=_h(target["from_user"])).status_code == 403
    res = client.post(f"/settlements/{target['id']}/received", headers=_h(owner)).json()
    assert res["status"] == "confirmed"

    # 미정산 배지: 4건 중 1건 확정 → 남은 3건
    unsettled = [r for r in client.get(f"/crews/{crew_id}/settlements", headers=_h(owner)).json() if r["unsettled"]]
    assert len(unsettled) == 3
