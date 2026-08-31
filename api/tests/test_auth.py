"""P6 실인증: Supabase JWT(ES256/JWKS) 검증 — 위조·만료·오디언스·prod 게이트.

JWKS는 테스트 키로 모킹 — 서명 검증 로직 자체는 실제 경로 그대로 탄다.
"""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.deps import get_db
from app.domain.models import Base
from app.infra import auth_jwt
from app.main import app

KID = "test-key"
SUB = "11111111-1111-1111-1111-111111111111"
_priv = ec.generate_private_key(ec.SECP256R1())
_other = ec.generate_private_key(ec.SECP256R1())  # 위조용 별개 키


def _jwk(pub) -> dict:
    d = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(pub))
    d["kid"] = KID
    return d


@pytest.fixture
def client(monkeypatch):
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
    monkeypatch.setattr(auth_jwt, "_jwks", lambda: {"keys": [_jwk(_priv.public_key())]})
    yield TestClient(app)
    app.dependency_overrides.clear()


def _token(sub=SUB, *, key=_priv, aud="authenticated", exp_delta=3600, kid=KID) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "aud": aud, "exp": now + exp_delta, "iat": now},
        key, algorithm="ES256", headers={"kid": kid},
    )


def _bearer(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


def test_jwt_signup_flow(client):
    t = _token()
    # 프로필 없으면 signup_required
    res = client.get("/me", headers=_bearer(t))
    assert res.status_code == 401 and res.json()["detail"] == "signup_required"
    # 가입: id = 토큰 sub, 본인인증 아님
    body = client.post("/users", json={"name": "부모"}, headers=_bearer(t)).json()
    assert body["id"] == SUB and body["identity_verified"] is False
    # 재가입 멱등
    assert client.post("/users", json={"name": "부모"}, headers=_bearer(t)).json()["id"] == SUB
    assert client.get("/me", headers=_bearer(t)).json()["id"] == SUB


def test_identity_verify_gates_crew_creation(client):
    """가입만으로는 크루를 못 만든다 — I1은 /identity/verify를 거쳐야 열린다."""
    t = _token()
    client.post("/users", json={"name": "부모"}, headers=_bearer(t))
    res = client.post("/crews", json={"name": "크루"}, headers=_bearer(t))
    assert res.status_code == 403 and res.json()["invariant"] == "I1"
    assert client.post("/identity/verify", headers=_bearer(t)).json()["identity_verified"] is True
    assert client.post("/crews", json={"name": "크루"}, headers=_bearer(t)).status_code == 200


def test_forged_token_rejected(client):
    assert client.get("/me", headers=_bearer(_token(key=_other))).status_code == 401


def test_expired_token_rejected(client):
    assert client.get("/me", headers=_bearer(_token(exp_delta=-10))).status_code == 401


def test_wrong_audience_rejected(client):
    assert client.get("/me", headers=_bearer(_token(aud="other"))).status_code == 401


def test_unknown_kid_rejected(client):
    assert client.get("/me", headers=_bearer(_token(kid="nope"))).status_code == 401


def test_prod_rejects_dev_header(client, monkeypatch):
    """배포 게이트: prod에서 X-User-Id는 죽고 Bearer만 산다."""
    from app.config import settings

    monkeypatch.setattr(settings, "env", "prod")
    assert client.get("/me", headers={"X-User-Id": "whatever"}).status_code == 401
    t = _token()
    client.post("/users", json={"name": "부모"}, headers=_bearer(t))
    assert client.get("/me", headers=_bearer(t)).status_code == 200
