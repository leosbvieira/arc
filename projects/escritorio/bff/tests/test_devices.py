import pytest
from fastapi.testclient import TestClient

from app import store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "devices.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_logout_remove_token_de_push_de_forma_idempotente(client):
    token = "ExponentPushToken[logout-safe]"
    assert client.post("/devices", json={"token": token}).status_code == 200
    assert store.list_devices() == [token]

    first = client.request("DELETE", "/devices", json={"token": token})
    retry = client.request("DELETE", "/devices", json={"token": token})

    assert first.json() == {"ok": True, "removed": 1}
    assert retry.json() == {"ok": True, "removed": 0}
    assert store.list_devices() == []
