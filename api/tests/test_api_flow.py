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


def test_full_week_flow(client):
    # 가입 (3가구)
    users = [client.post("/users", json={"name": f"가구{i}"}).json() for i in range(3)]
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
    outsider = client.post("/users", json={"name": "외부인"}).json()["id"]
    res = client.get(f"/crews/{crew_id}/sessions", headers=_h(outsider))
    assert res.status_code == 403 and res.json()["invariant"] == "I6"
