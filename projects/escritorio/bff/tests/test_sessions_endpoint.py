import pytest
from fastapi.testclient import TestClient

from app import main, store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_registra_sessao_leitura(client, monkeypatch):
    written = {}

    async def fake_raw(text, capture_id):
        written["text"] = text
        written["capture_id"] = capture_id
        return "1- Inbox/Raw/raw-cs1.md"

    monkeypatch.setattr(main.vault_client, "write_raw", fake_raw)
    notas = "quote: o vento apaga a vela"
    r = client.post(
        "/sessions",
        json={
            "tipo": "leitura",
            "livro": "Antifragil",
            "paginas": 12,
            "duracao_s": 1800,
            "notas": notas,
        },
    )

    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "session_id": 1,
        "raw_path": "1- Inbox/Raw/raw-cs1.md",
    }
    assert written == {"text": notas, "capture_id": "s1"}

    rows = store.list_sessions_since(0)
    assert rows[0]["livro"] == "Antifragil"
    assert rows[0]["duracao_s"] == 1800


def test_sessao_sem_notas_nao_grava_raw(client, monkeypatch):
    async def unexpected_raw(text, capture_id):
        raise AssertionError("write_raw não deveria ser chamado")

    monkeypatch.setattr(main.vault_client, "write_raw", unexpected_raw)
    r = client.post(
        "/sessions",
        json={
            "tipo": "leitura",
            "livro": "X",
            "paginas": 0,
            "duracao_s": 60,
            "notas": "",
        },
    )

    assert r.status_code == 200
    assert r.json()["raw_path"] is None


def test_paginas_none_quando_final_vazio(client, monkeypatch):
    async def unexpected_raw(text, capture_id):
        raise AssertionError("write_raw não deveria ser chamado")

    monkeypatch.setattr(main.vault_client, "write_raw", unexpected_raw)
    r = client.post(
        "/sessions",
        json={
            "tipo": "leitura",
            "livro": "X",
            "paginas": None,
            "duracao_s": 90,
            "notas": "",
        },
    )

    assert r.status_code == 200
    rows = store.list_sessions_since(0)
    assert rows[0]["paginas"] is None
