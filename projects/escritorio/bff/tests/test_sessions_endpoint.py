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
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    client.close()
    app.dependency_overrides.clear()


def test_registra_sessao_leitura(client, monkeypatch):
    written = {}

    async def fake_raw(text, capture_id, *, ts=None):
        written["text"] = text
        written["capture_id"] = capture_id
        return "1- Inbox/Raw/raw-cs1.md"

    monkeypatch.setattr(main.vault_client, "write_raw", fake_raw)
    notas = "quote: o vento apaga a vela"
    response = client.post(
        "/sessions",
        json={
            "tipo": "leitura",
            "livro": "Antifragil",
            "paginas": 12,
            "duracao_s": 1800,
            "notas": notas,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "session_id": 1,
        "raw_path": "1- Inbox/Raw/raw-cs1.md",
    }
    assert written == {"text": notas, "capture_id": "s1"}

    rows = store.list_sessions_since(0)
    assert rows[0]["livro"] == "Antifragil"
    assert rows[0]["duracao_s"] == 1800


def test_sessao_sem_notas_nao_grava_raw(client, monkeypatch):
    async def unexpected_raw(text, capture_id, *, ts=None):
        raise AssertionError("write_raw não deveria ser chamado")

    monkeypatch.setattr(main.vault_client, "write_raw", unexpected_raw)
    response = client.post(
        "/sessions",
        json={
            "tipo": "leitura",
            "livro": "X",
            "paginas": 0,
            "duracao_s": 60,
            "notas": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["raw_path"] is None


def test_paginas_none_quando_final_vazio(client, monkeypatch):
    async def unexpected_raw(text, capture_id, *, ts=None):
        raise AssertionError("write_raw não deveria ser chamado")

    monkeypatch.setattr(main.vault_client, "write_raw", unexpected_raw)
    response = client.post(
        "/sessions",
        json={
            "tipo": "leitura",
            "livro": "X",
            "paginas": None,
            "duracao_s": 90,
            "notas": "",
        },
    )

    assert response.status_code == 200
    rows = store.list_sessions_since(0)
    assert rows[0]["paginas"] is None


def test_retry_com_session_key_regrava_raw_idempotente(client, monkeypatch):
    written = []

    async def fake_raw(text, capture_id, *, ts=None):
        written.append({
            "text": text,
            "capture_id": capture_id,
            "ts": ts,
        })
        return "1- Inbox/Raw/raw-cs1.md"

    monkeypatch.setattr(main.vault_client, "write_raw", fake_raw)
    payload = {
        "tipo": "leitura",
        "livro": "Antifragil",
        "paginas": 12,
        "duracao_s": 1800,
        "notas": "quote: o vento apaga a vela",
        "session_key": "session-test-15",
    }

    first = client.post("/sessions", json=payload)
    retry = client.post("/sessions", json=payload)

    assert first.status_code == 200
    assert retry.status_code == 200
    assert first.json()["session_id"] == retry.json()["session_id"]
    assert first.json()["raw_path"] == "1- Inbox/Raw/raw-cs1.md"
    assert retry.json() == {
        "ok": True,
        "session_id": first.json()["session_id"],
        "raw_path": "1- Inbox/Raw/raw-cs1.md",
    }

    rows = store.list_sessions_since(0)
    assert len(rows) == 1
    assert rows[0]["session_key"] == "session-test-15"
    assert len(written) == 2
    assert written[0]["capture_id"] == f"s{first.json()['session_id']}"
    assert written[1]["capture_id"] == written[0]["capture_id"]
    assert written[1]["ts"] == written[0]["ts"] == rows[0]["inicio"]


def test_retry_apos_falha_do_raw_reusa_inicio_e_grava_uma_vez(
    client,
    monkeypatch,
):
    attempted_ts = []
    written = []

    async def flaky_raw(text, capture_id, *, ts=None):
        attempted_ts.append(ts)
        if len(attempted_ts) == 1:
            raise RuntimeError("falha sintética")
        written.append({"text": text, "capture_id": capture_id, "ts": ts})
        return "1- Inbox/Raw/raw-cs1.md"

    monkeypatch.setattr(main.vault_client, "write_raw", flaky_raw)
    payload = {
        "tipo": "leitura",
        "livro": "Antifragil",
        "paginas": 12,
        "duracao_s": 1800,
        "notas": "quote: o vento apaga a vela",
        "session_key": "session-write-failure-16",
    }

    first = client.post("/sessions", json=payload)
    retry = client.post("/sessions", json=payload)

    assert first.status_code == 500
    assert retry.status_code == 200
    assert retry.json() == {
        "ok": True,
        "session_id": 1,
        "raw_path": "1- Inbox/Raw/raw-cs1.md",
    }

    rows = store.list_sessions_since(0)
    assert len(rows) == 1
    assert attempted_ts[0] == attempted_ts[1] == rows[0]["inicio"]
    assert written == [{
        "text": payload["notas"],
        "capture_id": "s1",
        "ts": rows[0]["inicio"],
    }]
