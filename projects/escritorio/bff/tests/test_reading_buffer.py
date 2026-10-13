from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import hermes_client, main, store
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


def test_create_autosave_e_pending_preservam_verbatim_sem_tocar_servicos(
    client,
    monkeypatch,
):
    async def unexpected(*_args, **_kwargs):
        raise AssertionError("Hermes/vault não deve rodar no autosave")

    monkeypatch.setattr(main.hermes_client, "compile_reading", unexpected)
    monkeypatch.setattr(main.vault_client, "write_reading_note", unexpected)

    first = _create(client)
    retry = _create(client)
    assert first["created"] is True
    assert retry["created"] is False
    assert retry["session"]["id"] == first["session"]["id"]

    sid = first["session"]["id"]
    quote = 'O vento "apaga" a vela.\nSegunda linha intacta.'
    saved = _append(client, sid, 1, quote, "quote")
    repeated = _append(client, sid, 1, quote, "quote")
    assert saved.status_code == repeated.status_code == 200
    assert saved.json()["created"] is True
    assert repeated.json()["created"] is False
    assert repeated.json()["chunk"]["texto"] == quote

    assert _append(client, sid, 1, "texto diferente", "quote").status_code == 409
    assert _append(client, sid, 3, "pulou seq", "comentario").status_code == 409

    pending = client.get("/reading/sessions/pending").json()["sessions"]
    assert len(pending) == 1
    assert pending[0]["texto"] == quote
    assert len(pending[0]["buffer"]) == 1
    assert pending[0]["buffer"][0] | {"chunk_id": "<stable>"} == {
        "seq": 1,
        "chunk_id": "<stable>",
        "hook": "quote",
        "texto": quote,
        "ts": 1002.0,
    }


def test_compile_chama_hermes_e_vault_uma_vez_e_sugere_anki_sem_aprovar(
    client,
    monkeypatch,
):
    sid = _create(client)["session"]["id"]
    quote = "quote deve ficar palavra por palavra"
    assert _append(client, sid, 1, quote, "quote").status_code == 200

    calls = {"compile": 0, "vault": 0, "anki": 0}

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        calls["compile"] += 1
        assert livro == "Antifrágil"
        assert chunks[0]["texto"] == quote
        assert pagina_inicial == 10 and pagina_final == 25
        return f"# Antifrágil\n\n> {quote}"

    async def write_reading(markdown, reading_id, *, ts, client_key):
        calls["vault"] += 1
        assert quote in markdown and reading_id == sid and ts == 1_000.0
        assert client_key == "reading-1"
        return f"Leituras/2026-01-01 - leitura-r{reading_id}.md"

    async def suggest_anki(notas):
        calls["anki"] += 1
        assert f"quote: {quote}" in notas
        return [{"frente": "Frente", "meaning": "M", "example": "E", "hook": "H"}]

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)

    # Fluxo em dois passos: /draft gera o preview (Hermes), /compile aprova (vault+Anki).
    assert client.post(
        f"/reading/sessions/{sid}/draft", json={"pagina_final": 25}
    ).status_code == 200

    first = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 25, "fim": 1_120.0, "duracao_s": 75},
    )
    retry = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 25, "fim": 1_120.0, "duracao_s": 75},
    )

    assert first.status_code == retry.status_code == 200
    assert calls == {"compile": 1, "vault": 1, "anki": 1}
    assert first.json()["session"]["status"] == "compiled"
    assert first.json()["session"]["buffer"] == []
    assert first.json()["session"]["draft_md"] is None
    assert first.json()["anki_status"] == "done"
    assert retry.json()["session"]["vault_path"] == first.json()["session"]["vault_path"]
    cards = first.json()["anki_cards"]
    assert len(cards) == 1 and cards[0]["status"] == "sugerido"
    assert retry.json()["anki_cards"][0]["id"] == cards[0]["id"]

    sessions = store.list_sessions_since(0)
    assert len(sessions) == 1
    assert sessions[0]["duracao_s"] == 75
    assert sessions[0]["inicio"] == 1_045.0
    assert sessions[0]["session_key"] == f"reading:{sid}"


def test_duracao_de_cliente_antigo_nao_conta_varios_dias():
    assert main._reading_duration_s(1_000.0, 1_120.0, None) == 120
    assert main._reading_duration_s(1_000.0, 201_000.0, None) == 86_400
    assert main._reading_duration_s(1_000.0, 201_000.0, 75) == 75


@pytest.mark.parametrize("pagina_final", [-1, True, 1.5])
def test_compile_rejeita_pagina_final_invalida(client, pagina_final):
    sid = _create(client)["session"]["id"]
    resposta = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": pagina_final, "fim": 1_120.0, "duracao_s": 75},
    )
    assert resposta.status_code == 422


def test_falha_hermes_deixa_pending_e_buffer_continua_editavel(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    _append(client, sid, 1, "primeiro", "comentario")
    calls = {"compile": 0, "vault": 0}

    async def flaky_compile(*_args, **_kwargs):
        calls["compile"] += 1
        if calls["compile"] == 1:
            raise RuntimeError("payload secreto nunca deve ir ao log")
        return "# Nota final"

    async def write_reading(*_args, **_kwargs):
        calls["vault"] += 1
        return "Leituras/nota.md"

    monkeypatch.setattr(main.hermes_client, "compile_reading", flaky_compile)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", lambda *_: None)

    # O Hermes roda no /draft agora; a falha deixa a sessão pending e o buffer editável.
    failed = client.post(f"/reading/sessions/{sid}/draft", json={})
    assert failed.status_code == 502
    pending = client.get("/reading/sessions/pending").json()["sessions"][0]
    assert pending["status"] == "pending"
    assert pending["last_error"] == "RuntimeError"
    assert calls["vault"] == 0
    assert _append(client, sid, 2, "segundo", "ideia").status_code == 200

    async def no_cards(_notas):
        return []

    monkeypatch.setattr(main.hermes_client, "suggest_anki", no_cards)
    assert client.post(f"/reading/sessions/{sid}/draft", json={}).status_code == 200
    retried = client.post(f"/reading/sessions/{sid}/compile", json={"fim": 1_100})
    assert retried.status_code == 200
    assert calls == {"compile": 2, "vault": 1}

    with store._connect() as con:
        meta = "\n".join(
            row["meta_json"]
            for row in con.execute(
                "SELECT meta_json FROM telemetry WHERE evento = 'reading_compile_failed'"
            ).fetchall()
        )
    assert "payload secreto" not in meta
    assert "RuntimeError" in meta


def test_falha_vault_reusa_draft_e_congela_buffer(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    _append(client, sid, 1, "quote literal", "quote")
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
    assert client.post(f"/reading/sessions/{sid}/compile", json={"fim": 1_100}).status_code == 502
    pending = store.get_reading_session(sid)
    assert pending["status"] == "pending"
    assert pending["draft_md"].startswith("---\n")
    assert pending["draft_md"].endswith("# Draft persistido\n\nquote literal")
    blocked = _append(client, sid, 2, "não pode deixar draft stale", "texto")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "reading_draft_ja_gerado"

    retry = client.post(f"/reading/sessions/{sid}/compile", json={"fim": 1_100})
    assert retry.status_code == 200
    assert calls == {"compile": 1, "vault": 2}


def test_discard_e_explicito_idempotente_e_impede_compile(client, monkeypatch):
    sid = _create(client)["session"]["id"]
    _append(client, sid, 1, "conteúdo", "texto")

    first = client.post(f"/reading/sessions/{sid}/discard")
    retry = client.post(f"/reading/sessions/{sid}/discard")
    assert first.status_code == retry.status_code == 200
    assert retry.json()["session"]["status"] == "discarded"
    assert client.get("/reading/sessions/pending").json() == {"sessions": []}
    assert _append(client, sid, 2, "depois", "texto").status_code == 409
    assert client.post(f"/reading/sessions/{sid}/compile", json={}).status_code == 409


@pytest.mark.hermes_oneshot
async def test_oneshot_envia_prompt_longo_por_stdin_e_nao_argv(monkeypatch):
    prompt = "segredo-privado\n" * 10_000
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["input"] = kwargs.get("input")
        return type("Proc", (), {"returncode": 0, "stdout": "resposta", "stderr": ""})()

    monkeypatch.setattr(hermes_client, "_hermes_python", lambda: "python-hermes")
    monkeypatch.setattr(hermes_client.subprocess, "run", fake_run)

    assert await hermes_client._oneshot(prompt) == "resposta"
    assert seen["input"] == prompt
    assert "segredo-privado" not in " ".join(seen["args"])


@pytest.mark.hermes_oneshot
async def test_oneshot_sem_python_ao_lado_usa_o_binario_hermes_com_stdin(monkeypatch):
    """VPS: `hermes` é o wrapper do instalador oficial, sem venv/python junto. Antes
    disso o BFF levantava `hermes_error` em toda chamada (captura 52 de 12/out)."""
    prompt = "segredo-privado da captura"
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["input"] = kwargs.get("input")
        return type("Proc", (), {"returncode": 0, "stdout": "resposta", "stderr": "session_id: x"})()

    def sem_python():
        raise RuntimeError("hermes_error")

    monkeypatch.setattr(settings, "hermes_bin", "/opt/hermes/.local/bin/hermes")
    monkeypatch.setattr(hermes_client.shutil, "which", lambda _: None)
    monkeypatch.setattr(hermes_client, "_hermes_python", sem_python)
    monkeypatch.setattr(hermes_client.subprocess, "run", fake_run)

    assert await hermes_client._oneshot(prompt) == "resposta"
    assert seen["args"] == [
        "/opt/hermes/.local/bin/hermes", "chat", "--query-file", "-", "--quiet",
    ]
    assert seen["input"] == prompt
    assert "segredo-privado" not in " ".join(seen["args"])


async def test_compile_reading_insere_quote_verbatim_sem_enviar_ao_hermes(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)
    seen = {}

    async def structure(prompt):
        seen["prompt"] = prompt
        return "# Nota\n\n## Comentários\n\nUma reflexão."

    quote = "texto EXATO da citação: sem paráfrase"
    monkeypatch.setattr(hermes_client, "_oneshot", structure)
    draft = await hermes_client.compile_reading(
        "Livro",
        [
            {"seq": 1, "hook": "quote", "texto": quote},
            {"seq": 2, "hook": "comentario", "texto": "Uma reflexão."},
        ],
    )

    assert quote not in seen["prompt"]
    assert draft.endswith(f"## Citações\n\n{quote}")


async def test_compile_reading_so_quotes_e_deterministico(monkeypatch):
    monkeypatch.setattr(settings, "hermes_mock", False)

    async def unexpected(_prompt):
        raise AssertionError("Hermes não deve ser chamado para sessão só com citações")

    monkeypatch.setattr(hermes_client, "_oneshot", unexpected)
    draft = await hermes_client.compile_reading(
        "Livro\nInjetado",
        [
            {"seq": 1, "hook": "quote", "texto": "primeira"},
            {"seq": 2, "hook": "quote", "texto": "segunda"},
        ],
    )

    assert draft == "# Livro Injetado\n\n## Citações\n\nprimeira\n\nsegunda"


def test_export_anki_falha_de_arquivo_nao_marca_exportado(client, monkeypatch):
    card = store.add_anki_cards([{"frente": "F"}])[0]
    store.update_anki_card(card["id"], status="aprovado")

    def explode(*_args, **_kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(Path, "open", explode)
    response = client.post("/anki/export")
    assert response.status_code == 500
    assert store.get_anki_card(card["id"])["status"] == "aprovado"


@pytest.mark.parametrize(
    "cards",
    [[], [{"frente": "F", "meaning": "M", "example": "E", "hook": "H"}]],
)
def test_anki_suggestion_deduplica_por_session_id(client, monkeypatch, cards):
    calls = 0

    async def suggest(_notas):
        nonlocal calls
        calls += 1
        return cards

    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest)
    with store._connect() as con:
        con.execute(
            "INSERT INTO sessions "
            "(id, tipo, inicio, fim, duracao_s) VALUES (77, 'leitura', 1, 2, 1)"
        )
        con.commit()
    payload = {"notas": "comentario: nota", "session_id": 77}
    first = client.post("/anki/sugerir", json=payload)
    retry = client.post("/anki/sugerir", json=payload)
    assert first.status_code == retry.status_code == 200
    assert calls == 1
    assert retry.json() == first.json()
