import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _no_real_push(monkeypatch):
    """테스트가 실제 Expo 서버로 나가지 않게 한다.

    §29로 합류·승인에도 알림이 붙으면서 픽스처 단계에서 실 호출이 발생했고,
    Expo가 돌려준 DeviceNotRegistered로 테스트용 푸시 토큰이 지워졌다.
    """
    monkeypatch.setattr("app.infra.push.send", lambda msgs: [{"status": "ok"} for _ in msgs])
