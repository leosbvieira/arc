import copy
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main, reading_digest, store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _create(client, key="reading-reconcile-1") -> int:
    response = client.post(
        "/reading/sessions",
        json={
            "client_key": key,
            "livro": "Antifrágil — edição brasileira",
            "pagina_inicial": 10,
            "inicio": 1_000.0,
        },
    )
    assert response.status_code == 200
    return response.json()["session"]["id"]


def _append(client, session_id, seq, hook, texto):
    response = client.post(
        f"/reading/sessions/{session_id}/buffer",
        json={"seq": seq, "hook": hook, "texto": texto, "ts": 1_000 + seq},
    )
    assert response.status_code == 200


def _snapshot(key="reading-reconcile-1") -> dict:
    return {
        "client_key": key,
        "livro": "Antifrágil — edição brasileira",
        "pagina_inicial": 10,
        "pagina_final": 25,
        "buffer": [
            {
                "seq": 1,
                "hook": "quote",
                "texto": 'ação ≠ reação\r\n"quote" duplicado',
            },
            {
                "seq": 2,
                "hook": "comentario",
                "texto": "segunda linha",
            },
        ],
    }


def _prepare(client) -> int:
    sid = _create(client)
    for chunk in _snapshot()["buffer"]:
        _append(client, sid, chunk["seq"], chunk["hook"], chunk["texto"])
    return sid


def _compile(client, monkeypatch, sid, *, with_card=True):
    calls = {"hermes": 0, "vault": 0, "anki": 0}

    async def compile_reading(*_args, **_kwargs):
        calls["hermes"] += 1
        return "# Nota compilada"

    async def write_reading(*_args, **_kwargs):
        calls["vault"] += 1
        return "Leituras/nota-segura.md"

    async def suggest_anki(_notas):
        calls["anki"] += 1
        return [{"frente": "F", "meaning": "M"}] if with_card else []

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", write_reading)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", suggest_anki)

    # /draft gera o preview (Hermes) e /compile aprova (vault+Anki) — fluxo em dois passos.
    draft = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 25})
    assert draft.status_code == 200
    response = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 25, "fim": 1_120.0},
    )
    assert response.status_code == 200
    return response, calls


def test_digest_preserva_unicode_crlf_quotes_duplicados_e_ordena_por_seq():
    chunks = [
        {"seq": 1, "hook": "quote", "texto": 'ação\r\n"igual"'},
        {"seq": 2, "hook": "quote", "texto": 'ação\r\n"igual"'},
    ]
    args = {
        "client_key": "reading-key",
        "livro": "Café ☕",
        "pagina_inicial": None,
        "pagina_final": 9,
    }

    digest = reading_digest.source_digest(**args, chunks=chunks)
    assert digest == reading_digest.source_digest(**args, chunks=list(reversed(chunks)))
    assert digest != reading_digest.source_digest(**args, chunks=chunks[:1])
    changed = copy.deepcopy(chunks)
    changed[0]["texto"] = changed[0]["texto"].replace("\r\n", "\n")
    assert digest != reading_digest.source_digest(**args, chunks=changed)


def test_lost_response_reconcile_match_nao_repete_efeitos_e_devolve_cards(
    client,
    monkeypatch,
):
    sid = _prepare(client)
    compiled_response, calls = _compile(client, monkeypatch, sid)
    original_cards = compiled_response.json()["anki_cards"]

    # Simula resposta perdida: o cliente não usa o body do compile e reconcilia depois.
    first = client.post(f"/reading/sessions/{sid}/reconcile", json=_snapshot())
    retry = client.post(f"/reading/sessions/{sid}/reconcile", json=_snapshot())

    assert first.status_code == retry.status_code == 200
    assert first.json()["state"] == "compiled"
    assert first.json()["matched"] is True
    assert first.json()["anki_cards"] == retry.json()["anki_cards"] == original_cards
    assert calls == {"hermes": 1, "vault": 1, "anki": 1}

    session = first.json()["session"]
    assert len(session["source_digest"]) == 64
    assert session["buffer"] == []
    before = session["source_digest"]
    assert store.purge_reading_content(sid)["source_digest"] == before

    fetched = client.get(f"/reading/sessions/{sid}")
    assert fetched.status_code == 200
    assert fetched.json()["session"]["source_digest"] == before


def test_retry_com_draft_rejeita_snapshot_novo_antes_do_vault(client, monkeypatch):
    sid = _prepare(client)
    calls = {"hermes": 0, "vault": 0, "anki": 0}

    async def compile_reading(*_args, **_kwargs):
        calls["hermes"] += 1
        return "# Draft da pagina 25"

    async def flaky_vault(*_args, **_kwargs):
        calls["vault"] += 1
        if calls["vault"] == 1:
            raise RuntimeError("vault indisponivel")
        return "Leituras/retry-seguro.md"

    async def no_cards(_notas):
        calls["anki"] += 1
        return []

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    monkeypatch.setattr(main.vault_client, "write_reading_note", flaky_vault)
    monkeypatch.setattr(main.hermes_client, "suggest_anki", no_cards)

    # /draft persiste o preview antes do portão; o Hermes roda uma única vez aqui.
    assert client.post(
        f"/reading/sessions/{sid}/draft", json={"pagina_final": 25}
    ).status_code == 200

    first = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 25, "fim": 1_120.0},
    )
    assert first.status_code == 502
    pending = store.get_reading_session(sid)
    assert pending["draft_md"] == "# Draft da pagina 25"
    assert len(pending["source_digest"]) == 64

    divergent = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 26, "fim": 1_120.0},
    )
    assert divergent.status_code == 409
    assert divergent.json() == {"detail": "reading_draft_snapshot_divergente"}
    assert calls == {"hermes": 1, "vault": 1, "anki": 0}

    recovered = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 25, "fim": 1_120.0},
    )
    assert recovered.status_code == 200
    assert calls == {"hermes": 1, "vault": 2, "anki": 1}

    reconciled = client.post(f"/reading/sessions/{sid}/reconcile", json=_snapshot())
    assert reconciled.status_code == 200
    assert reconciled.json()["matched"] is True


@pytest.mark.parametrize(
    "mismatch",
    ["texto", "hook", "seq", "pagina_inicial", "pagina_final", "livro"],
)
def test_reconcile_compiled_rejeita_cada_snapshot_divergente(
    client,
    monkeypatch,
    mismatch,
):
    sid = _prepare(client)
    _, calls = _compile(client, monkeypatch, sid)
    snapshot = _snapshot()
    if mismatch == "texto":
        snapshot["buffer"][0]["texto"] += " alterado"
    elif mismatch == "hook":
        snapshot["buffer"][0]["hook"] = "ideia"
    elif mismatch == "seq":
        snapshot["buffer"][0]["seq"], snapshot["buffer"][1]["seq"] = 2, 1
    elif mismatch == "pagina_inicial":
        snapshot["pagina_inicial"] = 11
    elif mismatch == "pagina_final":
        snapshot["pagina_final"] = 26
    elif mismatch == "livro":
        snapshot["livro"] += " revisado"

    response = client.post(f"/reading/sessions/{sid}/reconcile", json=snapshot)

    assert response.status_code == 409
    assert response.json() == {"detail": "reading_compiled_snapshot_divergente"}
    assert calls == {"hermes": 1, "vault": 1, "anki": 1}


def test_compiled_legado_sem_digest_falha_sem_expor_conteudo(client, monkeypatch):
    sid = _prepare(client)
    _, calls = _compile(client, monkeypatch, sid)
    with store._connect() as con:
        con.execute("UPDATE reading_sessions SET source_digest = NULL WHERE id = ?", (sid,))
        con.commit()

    response = client.post(f"/reading/sessions/{sid}/reconcile", json=_snapshot())

    assert response.status_code == 409
    assert response.json() == {"detail": "reading_compiled_snapshot_nao_verificavel"}
    assert calls == {"hermes": 1, "vault": 1, "anki": 1}


def test_pending_reconcile_retorna_estado_sem_mutar(client):
    sid = _prepare(client)
    before = store.get_reading_session(sid)

    response = client.post(f"/reading/sessions/{sid}/reconcile", json=_snapshot())

    assert response.status_code == 200
    assert response.json() == {
        "state": "pending",
        "matched": False,
        "session": before,
        "anki_cards": [],
    }
    assert store.get_reading_session(sid) == before


def test_reconcile_estados_e_client_key_falham_fechado(client):
    sid = _prepare(client)
    wrong_key = _snapshot()
    wrong_key["client_key"] = "outra-client-key"
    response = client.post(f"/reading/sessions/{sid}/reconcile", json=wrong_key)
    assert response.status_code == 409
    assert response.json() == {"detail": "reading_client_key_divergente"}

    with store._connect() as con:
        con.execute(
            "UPDATE reading_sessions SET status = 'compiling', updated = ? WHERE id = ?",
            (9_999_999_999.0, sid),
        )
        con.commit()
    response = client.post(f"/reading/sessions/{sid}/reconcile", json=_snapshot())
    assert response.status_code == 409
    assert response.json() == {"detail": "reading_compile_em_andamento"}

    discarded_sid = _create(client, key="reading-discarded")
    _append(client, discarded_sid, 1, "texto", "conteúdo")
    assert client.post(f"/reading/sessions/{discarded_sid}/discard").status_code == 200
    discarded = _snapshot(key="reading-discarded")
    response = client.post(
        f"/reading/sessions/{discarded_sid}/reconcile",
        json=discarded,
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "reading_session_descartada"}

    response = client.post("/reading/sessions/999999/reconcile", json=_snapshot())
    assert response.status_code == 404
    assert response.json() == {"detail": "reading_session_nao_encontrada"}


def test_migracao_adiciona_source_digest_em_banco_legado(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as con:
        con.execute(
            "CREATE TABLE reading_sessions ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, client_key TEXT NOT NULL UNIQUE, "
            "livro TEXT NOT NULL, pagina_inicial INTEGER, pagina_final INTEGER, "
            "inicio REAL NOT NULL, fim REAL, status TEXT NOT NULL DEFAULT 'pending', "
            "last_seq INTEGER NOT NULL DEFAULT 0, draft_md TEXT, vault_path TEXT, "
            "compiled_session_id INTEGER, last_error TEXT, created REAL NOT NULL, "
            "updated REAL NOT NULL)"
        )
    monkeypatch.setattr(settings, "db_path", str(db_path))

    store.init_db()

    with store._connect() as con:
        columns = {row["name"] for row in con.execute("PRAGMA table_info(reading_sessions)")}
    assert "source_digest" in columns
