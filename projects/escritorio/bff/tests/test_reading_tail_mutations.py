import pytest
from fastapi.testclient import TestClient

from app import store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "tail.db"))
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _session(client: TestClient) -> int:
    response = client.post(
        "/reading/sessions",
        json={
            "client_key": "tail-session",
            "livro": "Antifragil",
            "pagina_inicial": 10,
            "inicio": 1_000,
        },
    )
    assert response.status_code == 200
    return response.json()["session"]["id"]


def _append(client: TestClient, session_id: int, seq: int, texto: str, hook="texto"):
    return client.post(
        f"/reading/sessions/{session_id}/buffer",
        json={"seq": seq, "hook": hook, "texto": texto, "ts": 1_000 + seq},
    )


def _chunk_id(client: TestClient, session_id: int, seq: int) -> str:
    chunks = client.get(f"/reading/sessions/{session_id}").json()["session"]["buffer"]
    return next(chunk["chunk_id"] for chunk in chunks if chunk["seq"] == seq)


def _patch(client, session_id, seq, body, *, expected_chunk_id=None):
    expected = expected_chunk_id or _chunk_id(client, session_id, seq)
    return client.patch(
        f"/reading/sessions/{session_id}/buffer/{seq}",
        json={"expected_chunk_id": expected, **body},
    )


def _delete(client, session_id, seq, *, expected_chunk_id):
    return client.delete(
        f"/reading/sessions/{session_id}/buffer/{seq}",
        params={"expected_chunk_id": expected_chunk_id},
    )


def test_patch_corrige_somente_cauda_e_retry_e_idempotente(client):
    sid = _session(client)
    assert _append(client, sid, 1, "primeiro").status_code == 200
    assert _append(client, sid, 2, "segundo", "comentario").status_code == 200

    blocked = _patch(client, sid, 1, {"texto": "nao pode"})
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "reading_apenas_ultimo_item_editavel"}

    first = _patch(client, sid, 2, {"texto": "segundo corrigido"})
    retry = _patch(client, sid, 2, {"texto": "segundo corrigido"})
    assert first.status_code == retry.status_code == 200
    assert first.json()["updated"] is True
    assert retry.json()["updated"] is False
    assert first.json()["chunk"] | {"chunk_id": "<stable>"} == {
        "seq": 2,
        "chunk_id": "<stable>",
        "hook": "comentario",
        "texto": "segundo corrigido",
        "ts": 1002.0,
    }

    hook_only = _patch(client, sid, 2, {"hook": "quote"})
    assert hook_only.status_code == 200
    assert hook_only.json()["updated"] is True
    assert hook_only.json()["chunk"]["texto"] == "segundo corrigido"
    assert hook_only.json()["chunk"]["ts"] == 1002.0

    session = client.get(f"/reading/sessions/{sid}").json()["session"]
    assert session["last_seq"] == 2
    assert session["texto"] == "primeiro\nsegundo corrigido"


def test_delete_remove_somente_cauda_atualiza_last_seq_e_retry(client):
    sid = _session(client)
    assert _append(client, sid, 1, "primeiro").status_code == 200
    assert _append(client, sid, 2, "segundo").status_code == 200

    id1 = _chunk_id(client, sid, 1)
    id2 = _chunk_id(client, sid, 2)
    blocked = _delete(client, sid, 1, expected_chunk_id=id1)
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "reading_apenas_ultimo_item_editavel"}

    first = _delete(client, sid, 2, expected_chunk_id=id2)
    retry = _delete(client, sid, 2, expected_chunk_id=id2)
    assert first.status_code == retry.status_code == 200
    assert first.json()["deleted"] is True
    assert retry.json()["deleted"] is False
    assert retry.json()["session"]["last_seq"] == 1
    remaining = retry.json()["session"]["buffer"]
    assert len(remaining) == 1
    assert remaining[0] | {"chunk_id": "<stable>"} == {
        "seq": 1,
        "chunk_id": "<stable>",
        "hook": "texto",
        "texto": "primeiro",
        "ts": 1001.0,
    }

    replacement = _append(client, sid, 2, "segundo novo", "ideia")
    assert replacement.status_code == 200
    assert replacement.json()["created"] is True
    assert client.get(f"/reading/sessions/{sid}").json()["session"]["last_seq"] == 2

    delayed_delete = _delete(client, sid, 2, expected_chunk_id=id2)
    delayed_patch = _patch(
        client,
        sid,
        2,
        {"texto": "retry velho"},
        expected_chunk_id=id2,
    )
    assert delayed_delete.status_code == delayed_patch.status_code == 409
    assert delayed_delete.json() == delayed_patch.json() == {
        "detail": "reading_item_foi_substituido"
    }

    replacement_id = _chunk_id(client, sid, 2)
    assert _delete(client, sid, 2, expected_chunk_id=replacement_id).status_code == 200
    emptied = _delete(client, sid, 1, expected_chunk_id=id1)
    empty_retry = _delete(client, sid, 1, expected_chunk_id=id1)
    assert emptied.status_code == empty_retry.status_code == 200
    assert emptied.json()["deleted"] is True
    assert empty_retry.json()["deleted"] is False
    assert empty_retry.json()["session"]["last_seq"] == 0
    assert empty_retry.json()["session"]["buffer"] == []

    with store._connect() as con:
        deleted_events = con.execute(
            "SELECT COUNT(*) FROM telemetry "
            "WHERE evento = 'reading_buffer_deleted' AND ref = ?",
            (str(sid),),
        ).fetchone()[0]
    assert deleted_events == 3


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_mutacao_rejeita_sessao_com_draft(client, method):
    sid = _session(client)
    assert _append(client, sid, 1, "conteudo").status_code == 200
    with store._connect() as con:
        con.execute(
            "UPDATE reading_sessions SET draft_md = ? WHERE id = ?",
            ("# draft", sid),
        )
        con.commit()

    if method == "patch":
        response = _patch(client, sid, 1, {"texto": "corrigido"})
    else:
        response = _delete(
            client,
            sid,
            1,
            expected_chunk_id=_chunk_id(client, sid, 1),
        )
    assert response.status_code == 409
    assert response.json() == {"detail": "reading_draft_ja_gerado"}


@pytest.mark.parametrize("method", ["patch", "delete"])
@pytest.mark.parametrize("status", ["compiling", "compiled", "discarded"])
def test_mutacao_rejeita_status_nao_editavel(client, method, status):
    sid = _session(client)
    assert _append(client, sid, 1, "conteudo").status_code == 200
    with store._connect() as con:
        con.execute(
            "UPDATE reading_sessions SET status = ? WHERE id = ?",
            (status, sid),
        )
        con.commit()

    if method == "patch":
        response = _patch(client, sid, 1, {"texto": "corrigido"})
    else:
        response = _delete(
            client,
            sid,
            1,
            expected_chunk_id=_chunk_id(client, sid, 1),
        )
    assert response.status_code == 409
    assert response.json() == {"detail": "reading_session_nao_editavel"}


def test_mutacoes_validam_seq_payload_e_sessao(client):
    sid = _session(client)
    assert _append(client, sid, 1, "conteudo").status_code == 200

    chunk_id = _chunk_id(client, sid, 1)
    empty_patch = client.patch(
        f"/reading/sessions/{sid}/buffer/1",
        json={"expected_chunk_id": chunk_id},
    )
    blank_patch = _patch(client, sid, 1, {"texto": "   "})
    missing_item = client.patch(
        f"/reading/sessions/{sid}/buffer/3",
        json={"expected_chunk_id": "missing", "texto": "corrigido"},
    )
    delete_missing = _delete(
        client,
        sid,
        3,
        expected_chunk_id="missing",
    )

    assert empty_patch.status_code == blank_patch.status_code == 422
    assert client.patch(
        f"/reading/sessions/{sid}/buffer/0",
        json={"expected_chunk_id": chunk_id, "texto": "corrigido"},
    ).status_code == 422
    assert _delete(client, sid, 0, expected_chunk_id=chunk_id).status_code == 422
    assert missing_item.status_code == delete_missing.status_code == 404
    assert missing_item.json() == delete_missing.json() == {
        "detail": "reading_item_nao_encontrado"
    }
    assert _delete(client, 999999, 1, expected_chunk_id="missing").status_code == 404
