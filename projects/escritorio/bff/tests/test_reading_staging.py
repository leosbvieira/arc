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
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _create(client, *, key="reading-1", inicio=1_000.0):
    response = client.post(
        "/reading/sessions",
        json={
            "client_key": key,
            "livro": "Antifrágil",
            "pagina_inicial": 10,
            "inicio": inicio,
        },
    )
    assert response.status_code == 200
    return response.json()


def _append(client, session_id, seq, texto, hook="texto"):
    return client.post(
        f"/reading/sessions/{session_id}/buffer",
        json={"seq": seq, "hook": hook, "texto": texto, "ts": 1_001 + seq},
    )


def test_draft_gera_preview_sem_tocar_vault_e_deixa_staged(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    quote = "trecho literal para o preview"
    assert _append(client, sid, 1, quote, "quote").status_code == 200

    calls = {"compile": 0}

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        calls["compile"] += 1
        assert livro == "Antifrágil"
        assert chunks[0]["texto"] == quote
        assert pagina_inicial == 10 and pagina_final == 40
        return f"# Preview\n\n> {quote}"

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("vault/anki não deve rodar no /draft")

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", unexpected)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", unexpected)

    resp = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 40})
    assert resp.status_code == 200
    body = resp.json()
    assert body["draft_md"] == f"# Preview\n\n> {quote}"
    assert body["session"]["status"] == "pending"
    assert body["session"]["draft_md"] == f"# Preview\n\n> {quote}"
    assert calls["compile"] == 1

    staged = store.get_reading_session(sid)
    assert staged["status"] == "pending"
    assert staged["draft_md"] == f"# Preview\n\n> {quote}"
    assert staged["buffer"][0]["texto"] == quote


def test_segundo_draft_com_mesmo_buffer_e_idempotente(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    assert _append(client, sid, 1, "conteúdo", "comentario").status_code == 200

    calls = {"compile": 0}

    async def compile_reading(*_args, **_kwargs):
        calls["compile"] += 1
        return "# Preview estável"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)

    first = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 30})
    second = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 30})
    assert first.status_code == second.status_code == 200
    assert calls["compile"] == 1
    assert first.json()["draft_md"] == second.json()["draft_md"] == "# Preview estável"
    assert second.json()["session"]["status"] == "pending"


def test_editar_buffer_enquanto_staged_congela_com_409(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    assert _append(client, sid, 1, "primeiro", "comentario").status_code == 200

    async def compile_reading(*_args, **_kwargs):
        return "# Preview"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    assert client.post(f"/reading/sessions/{sid}/draft", json={}).status_code == 200

    blocked = _append(client, sid, 2, "segundo", "ideia")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "reading_draft_ja_gerado"


def test_compile_sem_draft_previo_recusa_com_422(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    assert _append(client, sid, 1, "conteúdo", "comentario").status_code == 200

    async def unexpected(*_args, **_kwargs):
        raise AssertionError("nada deve rodar sem draft")

    monkeypatch.setattr(main.hermes_client, "compile_reading", unexpected)
    monkeypatch.setattr(main.vault_client, "write_reading_note", unexpected)

    resp = client.post(f"/reading/sessions/{sid}/compile", json={"fim": 1_100})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "reading_draft_ausente"

    # Sem draft, segue pending e editável (o release não congela nada).
    again = store.get_reading_session(sid)
    assert again["status"] == "pending"
    assert again["draft_md"] is None
    assert _append(client, sid, 2, "mais", "ideia").status_code == 200


def test_compile_apos_draft_grava_vault_e_sugere_anki(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    quote = "citação verbatim"
    assert _append(client, sid, 1, quote, "quote").status_code == 200

    calls = {"compile": 0, "vault": 0, "anki": 0}

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        calls["compile"] += 1
        return f"# Nota\n\n> {quote}"

    async def write_reading(markdown, reading_id, *, ts, client_key):
        calls["vault"] += 1
        assert quote in markdown and reading_id == sid and ts == 1_000.0
        assert client_key == "reading-1"
        return f"Leituras/leitura-r{reading_id}.md"

    async def suggest_anki(notas):
        calls["anki"] += 1
        assert f"quote: {quote}" in notas
        return [{"frente": "F", "meaning": "M", "example": "E", "hook": "H"}]

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)

    draft = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 25})
    assert draft.status_code == 200
    assert calls == {"compile": 1, "vault": 0, "anki": 0}

    approve = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 25, "fim": 1_120.0, "duracao_s": 75},
    )
    assert approve.status_code == 200
    # O draft já existia: /compile NÃO chama o Hermes de novo (bloco gera-se-faltar removido).
    assert calls == {"compile": 1, "vault": 1, "anki": 1}
    sess = approve.json()["session"]
    assert sess["status"] == "compiled"
    assert sess["draft_md"] is None
    assert sess["buffer"] == []
    assert approve.json()["anki_status"] == "done"
    cards = approve.json()["anki_cards"]
    assert len(cards) == 1 and cards[0]["status"] == "sugerido"


def test_compile_com_pagina_final_diferente_do_draft_diverge(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    assert _append(client, sid, 1, "conteúdo", "comentario").status_code == 200

    async def compile_reading(*_args, **_kwargs):
        return "# Preview"

    async def unexpected_vault(*_args, **_kwargs):
        raise AssertionError("vault não deve rodar quando o snapshot diverge")

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", unexpected_vault)

    assert (
        client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 25}).status_code
        == 200
    )
    diverge = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 40, "fim": 1_100},
    )
    assert diverge.status_code == 409
    assert diverge.json()["detail"] == "reading_draft_snapshot_divergente"

    # Segue staged: o release preserva draft_md (pending + draft).
    staged = store.get_reading_session(sid)
    assert staged["status"] == "pending"
    assert staged["draft_md"] == "# Preview"


def test_rejeitar_draft_reabre_edicao_do_buffer(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    assert _append(client, sid, 1, "primeiro", "comentario").status_code == 200

    async def compile_reading(*_args, **_kwargs):
        return "# Preview"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    assert client.post(f"/reading/sessions/{sid}/draft", json={}).status_code == 200
    # Congelado enquanto staged.
    assert _append(client, sid, 2, "bloqueado", "ideia").status_code == 409

    reject = client.delete(f"/reading/sessions/{sid}/draft")
    assert reject.status_code == 200
    assert reject.json()["session"]["status"] == "pending"
    assert reject.json()["session"]["draft_md"] is None

    # Editável de novo, buffer intacto (o chunk 1 continua lá).
    assert _append(client, sid, 2, "segundo", "ideia").status_code == 200
    again = store.get_reading_session(sid)
    assert [c["texto"] for c in again["buffer"]] == ["primeiro", "segundo"]


def test_falha_vault_no_compile_mantem_staged_e_retry_reusa_draft(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    assert _append(client, sid, 1, "quote literal", "quote").status_code == 200

    calls = {"compile": 0, "vault": 0}

    async def compile_reading(*_args, **_kwargs):
        calls["compile"] += 1
        return "# Draft persistido\n\nquote literal"

    async def flaky_vault(*_args, **_kwargs):
        calls["vault"] += 1
        if calls["vault"] == 1:
            raise RuntimeError("vault caiu")
        return "Leituras/nota.md"

    async def no_cards(_notas):
        return []

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", flaky_vault)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", no_cards)

    assert client.post(f"/reading/sessions/{sid}/draft", json={}).status_code == 200
    assert calls == {"compile": 1, "vault": 0}

    fail = client.post(f"/reading/sessions/{sid}/compile", json={"fim": 1_100})
    assert fail.status_code == 502
    staged = store.get_reading_session(sid)
    assert staged["status"] == "pending"
    assert staged["draft_md"] == "# Draft persistido\n\nquote literal"
    # Buffer segue congelado enquanto o draft sobrevive.
    blocked = _append(client, sid, 2, "não pode deixar draft stale", "texto")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "reading_draft_ja_gerado"

    retry = client.post(f"/reading/sessions/{sid}/compile", json={"fim": 1_100})
    assert retry.status_code == 200
    # Draft reusado: Hermes uma vez (no /draft), vault duas (falha + sucesso).
    assert calls == {"compile": 1, "vault": 2}
    assert retry.json()["session"]["status"] == "compiled"


def test_list_pending_inclui_a_sessao_staged(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    assert _append(client, sid, 1, "conteúdo", "comentario").status_code == 200

    async def compile_reading(*_args, **_kwargs):
        return "# Preview staged"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    assert client.post(f"/reading/sessions/{sid}/draft", json={}).status_code == 200

    pending = client.get("/reading/sessions/pending").json()["sessions"]
    assert len(pending) == 1
    assert pending[0]["id"] == sid
    assert pending[0]["status"] == "pending"
    assert pending[0]["draft_md"] == "# Preview staged"
