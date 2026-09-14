"""네이버 로그인(자체 발급자) — 이중 발급자 검증·위조 차단·state·I1 연결.

Supabase는 그대로 두고 네이버만 우리가 서명한다. 두 발급자가 섞여도 안전해야 한다.
"""

import time

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.deps import get_db
from app.domain.models import Base, User
from app.infra import local_jwt, naver_oauth
from app.main import app

SECRET = "test-secret-please-rotate"


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
    monkeypatch.setattr(settings, "jwt_secret", SECRET)
    monkeypatch.setattr(settings, "naver_client_id", "cid")
    monkeypatch.setattr(settings, "naver_client_secret", "csec")
    monkeypatch.setattr(settings, "web_origin", "https://with-care-web.fly.dev")
    yield TestClient(app)
    app.dependency_overrides.clear()


def _bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def _fake_naver(monkeypatch, *, mobile=None, email="user@naver.com", nid="naver-123"):
    monkeypatch.setattr(naver_oauth, "exchange", lambda code, state: "naver-access")
    monkeypatch.setattr(
        naver_oauth, "profile",
        lambda tok: {"id": nid, "email": email, "name": "부모", **({"mobile": mobile} if mobile else {})},
    )


def test_providers_flag(client):
    assert client.get("/auth/providers").json()["naver"] is True


def test_naver_login_issues_working_token(client, monkeypatch):
    """네이버 콜백 → 우리 JWT → 그 토큰으로 가입·조회가 된다."""
    _fake_naver(monkeypatch)
    state = client.get("/auth/naver/start", follow_redirects=False).headers["location"].split("state=")[1]
    res = client.get(f"/auth/naver/callback?code=abc&state={state}", follow_redirects=False)
    assert res.status_code in (302, 307)
    token = res.headers["location"].split("#token=")[1].split("&")[0]

    body = client.post("/users", json={"name": "부모"}, headers=_bearer(token)).json()
    assert client.get("/me", headers=_bearer(token)).json()["id"] == body["id"]


def test_naver_id_is_stable_across_logins(client, monkeypatch):
    """같은 네이버 계정은 언제 로그인해도 같은 사용자다."""
    _fake_naver(monkeypatch)
    ids = []
    for _ in range(2):
        state = client.get("/auth/naver/start", follow_redirects=False).headers["location"].split("state=")[1]
        loc = client.get(f"/auth/naver/callback?code=abc&state={state}", follow_redirects=False).headers["location"]
        tok = loc.split("#token=")[1].split("&")[0]
        ids.append(jwt.decode(tok, SECRET, algorithms=["HS256"], audience="authenticated", issuer="with-care")["sub"])
    assert ids[0] == ids[1]


def test_naver_mobile_satisfies_identity_gate(client, monkeypatch):
    """네이버가 휴대폰을 넘겨주면 본인인증(phone 수단)을 통과한다 — 아니면 막힌다."""
    monkeypatch.setattr(settings, "identity_method", "phone")

    _fake_naver(monkeypatch, mobile=None, nid="no-phone")
    state = client.get("/auth/naver/start", follow_redirects=False).headers["location"].split("state=")[1]
    tok = client.get(f"/auth/naver/callback?code=a&state={state}", follow_redirects=False).headers["location"].split("#token=")[1].split("&")[0]
    client.post("/users", json={"name": "무전화"}, headers=_bearer(tok))
    assert client.post("/identity/verify", headers=_bearer(tok)).status_code == 403

    _fake_naver(monkeypatch, mobile="010-1234-5678", nid="with-phone")
    state = client.get("/auth/naver/start", follow_redirects=False).headers["location"].split("state=")[1]
    tok2 = client.get(f"/auth/naver/callback?code=a&state={state}", follow_redirects=False).headers["location"].split("#token=")[1].split("&")[0]
    client.post("/users", json={"name": "유전화"}, headers=_bearer(tok2))
    assert client.post("/identity/verify", headers=_bearer(tok2)).json()["identity_verified"] is True


def test_forged_local_token_rejected(client):
    """다른 키로 서명한 우리-발급자 사칭 토큰은 거부된다."""
    now = int(time.time())
    forged = jwt.encode(
        {"sub": "x", "aud": "authenticated", "iss": "with-care", "iat": now, "exp": now + 3600},
        "wrong-secret", algorithm="HS256",
    )
    assert client.get("/me", headers=_bearer(forged)).status_code == 401


def test_alg_none_rejected(client):
    """alg=none 혼동 공격 차단."""
    now = int(time.time())
    tok = jwt.encode(
        {"sub": "x", "aud": "authenticated", "iss": "with-care", "iat": now, "exp": now + 3600},
        key="", algorithm="none",
    )
    assert client.get("/me", headers=_bearer(tok)).status_code == 401


def test_expired_local_token_rejected(client, monkeypatch):
    now = int(time.time())
    tok = jwt.encode(
        {"sub": "x", "aud": "authenticated", "iss": "with-care", "iat": now - 7200, "exp": now - 10},
        SECRET, algorithm="HS256",
    )
    assert client.get("/me", headers=_bearer(tok)).status_code == 401


def test_unknown_state_rejected(client, monkeypatch):
    """CSRF: 서버가 발급하지 않은 state는 거부한다."""
    _fake_naver(monkeypatch)
    assert client.get("/auth/naver/callback?code=abc&state=forged", follow_redirects=False).status_code == 400


def test_state_is_single_use(client, monkeypatch):
    _fake_naver(monkeypatch)
    state = client.get("/auth/naver/start", follow_redirects=False).headers["location"].split("state=")[1]
    assert client.get(f"/auth/naver/callback?code=a&state={state}", follow_redirects=False).status_code in (302, 307)
    assert client.get(f"/auth/naver/callback?code=a&state={state}", follow_redirects=False).status_code == 400


def test_disabled_without_secret(client, monkeypatch):
    """키가 없으면 기능 자체가 꺼진다 (fail-closed)."""
    monkeypatch.setattr(settings, "jwt_secret", "")
    assert client.get("/auth/providers").json()["naver"] is False
    assert client.get("/auth/naver/start", follow_redirects=False).status_code == 503
