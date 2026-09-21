"""§29: 다회용 초대 + 승인 관문 — HTTP 경계에서의 검증.

도메인 단위 검증은 tests/invariants/test_invariants.py에 있다. 여기서는 라우터가
그 가드를 우회하는 경로를 만들지 않았는지를 본다.
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


def _h(uid):
    return {"X-User-Id": uid}


def _user(client, name):
    uid = client.post("/users", json={"name": name}).json()["id"]
    client.post("/identity/verify", headers=_h(uid))
    return uid


@pytest.fixture
def crew(client):
    owner = _user(client, "오너")
    crew_id = client.post("/crews", json={"name": "초대크루"}, headers=_h(owner)).json()["id"]
    token = client.post(f"/crews/{crew_id}/invites", headers=_h(owner)).json()["token"]
    return {"owner": owner, "crew_id": crew_id, "token": token}


def test_one_link_serves_many_households(client, crew):
    """§29의 존재 이유: 단톡방에 링크 하나를 붙이면 여러 집이 들어온다."""
    for name in ("지우네", "서준네", "하윤네"):
        uid = _user(client, name)
        r = client.post(f"/invites/{crew['token']}/join", headers=_h(uid))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"
        req_id = r.json()["request_id"]
        ok = client.post(
            f"/crews/{crew['crew_id']}/join-requests/{req_id}",
            json={"approve": True},
            headers=_h(crew["owner"]),
        )
        assert ok.status_code == 200
    assert client.get(f"/crews/{crew['crew_id']}", headers=_h(crew["owner"])).json()["member_count"] == 4


def test_pending_applicant_sees_nothing(client, crew):
    """승인 전에는 멤버가 아니다 — 크루 데이터도, 대기 목록도 볼 수 없다 (I6)."""
    uid = _user(client, "신청만한사람")
    client.post(f"/invites/{crew['token']}/join", headers=_h(uid))
    assert client.get(f"/crews/{crew['crew_id']}", headers=_h(uid)).status_code == 403
    assert client.get(f"/crews/{crew['crew_id']}/join-requests", headers=_h(uid)).status_code == 403
    assert client.get(f"/my/crews", headers=_h(uid)).json() == []


def test_outsider_cannot_approve(client, crew):
    uid = _user(client, "신청자")
    req_id = client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).json()["request_id"]
    outsider = _user(client, "남")
    r = client.post(
        f"/crews/{crew['crew_id']}/join-requests/{req_id}",
        json={"approve": True},
        headers=_h(outsider),
    )
    assert r.status_code == 403


def test_applicant_cannot_self_approve(client, crew):
    uid = _user(client, "셀프승인시도")
    req_id = client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).json()["request_id"]
    r = client.post(
        f"/crews/{crew['crew_id']}/join-requests/{req_id}",
        json={"approve": True},
        headers=_h(uid),
    )
    assert r.status_code == 403


def test_seats_are_capped(client, crew):
    """기본 정원 5집. 링크가 무한 관문이 되지 않는다."""
    for i in range(5):
        uid = _user(client, f"집{i}")
        assert client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).status_code == 200
    over = _user(client, "여섯번째")
    r = client.post(f"/invites/{crew['token']}/join", headers=_h(over))
    assert r.status_code == 403
    assert client.get(f"/invites/{crew['token']}").json()["seats_left"] == 0


def test_rejection_returns_the_seat(client, crew):
    """거절은 자리를 돌려준다 — 잘못 들어온 사람 때문에 링크가 막히지 않게."""
    uid = _user(client, "거절될사람")
    req_id = client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).json()["request_id"]
    assert client.get(f"/invites/{crew['token']}").json()["seats_left"] == 4
    client.post(
        f"/crews/{crew['crew_id']}/join-requests/{req_id}",
        json={"approve": False},
        headers=_h(crew["owner"]),
    )
    assert client.get(f"/invites/{crew['token']}").json()["seats_left"] == 5
    # 거절당한 본인은 같은 링크로 다시 신청할 수 없다
    assert client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).status_code == 403


def test_repeated_taps_make_one_request(client, crew):
    """카톡에서 링크를 두 번 눌러도 대기 줄은 하나 (멱등)."""
    uid = _user(client, "두번누른사람")
    a = client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).json()
    b = client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).json()
    assert a["request_id"] == b["request_id"]
    assert len(client.get(f"/crews/{crew['crew_id']}/join-requests", headers=_h(crew["owner"])).json()) == 1


def test_unverified_cannot_even_request(client, crew):
    """I1은 그대로다 — 본인인증 없이는 대기 줄에도 못 선다."""
    uid = client.post("/users", json={"name": "미인증"}).json()["id"]
    assert client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).status_code == 403


def test_approval_notifies_applicant(client, crew):
    """승인/거절 결과는 신청자 본인에게 간다 — 기다리는 사람이 방치되지 않게."""
    uid = _user(client, "알림받을사람")
    req_id = client.post(f"/invites/{crew['token']}/join", headers=_h(uid)).json()["request_id"]
    client.post(
        f"/crews/{crew['crew_id']}/join-requests/{req_id}",
        json={"approve": True},
        headers=_h(crew["owner"]),
    )
    titles = [n["title"] for n in client.get("/me/notifications", headers=_h(uid)).json()]
    assert "합류가 승인됐어요" in titles
    # 초대한 사람에게는 신청이 왔다는 알림이 가 있다
    owner_titles = [n["title"] for n in client.get("/me/notifications", headers=_h(crew["owner"])).json()]
    assert "합류 신청이 왔어요" in owner_titles
