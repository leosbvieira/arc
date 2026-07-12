import pytest
from fastapi.testclient import TestClient

from app import store, telegram
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "internal_token", "itok")
    store.init_db()
    return TestClient(app)


def test_nudge_closing(client, monkeypatch):
    sent = []

    async def fake_send(text):
        sent.append(text)
        return True

    monkeypatch.setattr(telegram, "send", fake_send)
    r = client.post(
        "/internal/nudge",
        json={"kind": "closing"},
        headers={"X-Internal-Token": "itok"},
    )
    assert r.status_code == 200 and sent and "fechar o dia" in sent[0]


def test_nudge_kind_invalido(client):
    r = client.post(
        "/internal/nudge",
        json={"kind": "xxx"},
        headers={"X-Internal-Token": "itok"},
    )
    assert r.status_code == 422


def test_nudge_token_errado(client):
    r = client.post(
        "/internal/nudge",
        json={"kind": "closing"},
        headers={"X-Internal-Token": "nope"},
    )
    assert r.status_code == 403
