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


def _nova_obra(client, titulo="Sapiens"):
    resp = client.post("/reading/books", json={"titulo": titulo})
    assert resp.status_code == 200
    return resp.json()["book"]


def test_criar_obra_e_idempotente_por_slug(client):
    primeira = client.post("/reading/books", json={"titulo": "Sapiens"})
    segunda = client.post("/reading/books", json={"titulo": "sapiens "})
    assert primeira.json()["created"] is True
    assert segunda.json()["created"] is False
    assert segunda.json()["book"]["id"] == primeira.json()["book"]["id"]


def test_criar_obra_com_titulo_vazio(client):
    resp = client.post("/reading/books", json={"titulo": "   "})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "titulo_invalido"


def test_listar_estante(client):
    _nova_obra(client, "Sapiens")
    resp = client.get("/reading/books")
    assert resp.status_code == 200
    linha = resp.json()["books"][0]
    assert linha["titulo"] == "Sapiens"
    assert linha["pagina_atual"] is None
    assert linha["sessoes_n"] == 0


def test_terminar_pela_api(client):
    obra = _nova_obra(client)
    assert client.post(f"/reading/books/{obra['id']}/terminar").status_code == 200
    assert client.get("/reading/books").json()["books"] == []
    assert len(client.get("/reading/books?status=terminado").json()["books"]) == 1

    repetido = client.post(f"/reading/books/{obra['id']}/terminar")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "book_ja_terminado"


def test_reabrir_pela_api(client):
    obra = _nova_obra(client)
    client.post(f"/reading/books/{obra['id']}/terminar")
    resp = client.post(f"/reading/books/{obra['id']}/reabrir")
    assert resp.status_code == 200
    assert resp.json()["book"]["ciclo"] == 2

    repetido = client.post(f"/reading/books/{obra['id']}/reabrir")
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "book_ja_lendo"


def test_endpoints_de_obra_inexistente(client):
    assert client.post("/reading/books/9999/terminar").status_code == 404
    assert client.post("/reading/books/9999/reabrir").status_code == 404


def test_terminar_com_sessao_aberta_pela_api(client):
    obra = _nova_obra(client)
    client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": obra["id"]},
    )
    resp = client.post(f"/reading/books/{obra['id']}/terminar")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "book_com_sessao_aberta"


def test_sessao_com_book_id_usa_o_titulo_canonico(client):
    obra = _nova_obra(client)
    resp = client.post(
        "/reading/sessions",
        json={
            "client_key": "s1",
            "livro": "TÍTULO MENTIROSO",
            "pagina_inicial": 10,
            "inicio": 1_000.0,
            "book_id": obra["id"],
        },
    )
    assert resp.status_code == 200
    sessao = resp.json()["session"]
    assert sessao["livro"] == "Sapiens"
    assert sessao["book_id"] == obra["id"]
    assert sessao["book_ciclo"] == 1


def test_sessao_com_book_id_inexistente_da_422(client):
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": 9999},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "book_nao_encontrado"


def test_sessao_em_obra_terminada_da_409(client):
    obra = _nova_obra(client)
    client.post(f"/reading/books/{obra['id']}/terminar")
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "x", "inicio": 1.0, "book_id": obra["id"]},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "book_nao_aceita_sessao"


def test_sessao_sem_book_id_segue_o_caminho_antigo(client):
    resp = client.post(
        "/reading/sessions",
        json={"client_key": "s1", "livro": "Livro solto", "inicio": 1.0},
    )
    assert resp.status_code == 200
    assert resp.json()["session"]["book_id"] is None


def _sessao_com_buffer(client, obra_id=None):
    corpo = {"client_key": "s1", "livro": "Sapiens", "pagina_inicial": 190, "inicio": 1.0}
    if obra_id is not None:
        corpo["book_id"] = obra_id
    sid = client.post("/reading/sessions", json=corpo).json()["session"]["id"]
    client.post(
        f"/reading/sessions/{sid}/buffer",
        json={"seq": 1, "hook": "comentario", "texto": "um comentário", "ts": 2.0},
    )
    return sid


def test_draft_prefixa_o_frontmatter_antes_do_staging(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)

    resp = client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert resp.status_code == 200
    draft = resp.json()["draft_md"]
    assert draft.startswith("---\n")
    assert 'livro: "Sapiens"' in draft
    assert "paginas: 190-214" in draft
    assert draft.endswith("# Nota do Hermes")
    # O que ficou staged é o documento COMPLETO: é ele que o Leo aprova.
    assert store.get_reading_session(sid)["draft_md"] == draft
    assert store.get_reading_session(sid)["draft_fmt"] == 2


def test_compile_recusa_draft_legado(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})

    # Simula o preview que já estava aberto no celular quando o deploy subiu.
    with store.closing(store._connect()) as con:
        con.execute("UPDATE reading_sessions SET draft_fmt = NULL WHERE id = ?", (sid,))
        con.commit()

    async def nunca(*_a, **_k):
        raise AssertionError("o vault não pode ser tocado com draft legado")

    monkeypatch.setattr(main.vault_client, "write_reading_note", nunca)

    resp = client.post(
        f"/reading/sessions/{sid}/compile",
        json={"pagina_final": 214, "fim": 100.0, "duracao_s": 60},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "reading_draft_desatualizado"
    assert store.get_reading_session(sid)["status"] == "pending"


def test_draft_legado_e_regenerado_e_nao_reusado(client, monkeypatch):
    obra = _nova_obra(client)
    sid = _sessao_com_buffer(client, obra["id"])
    chamadas = {"n": 0}

    async def compile_reading(livro, chunks, pagina_inicial=None, pagina_final=None):
        chamadas["n"] += 1
        return "# Nota do Hermes"

    monkeypatch.setattr(main.hermes_client, "compile_reading", compile_reading)
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 1

    # Mesmo digest, mas formato antigo: tem que regenerar.
    with store.closing(store._connect()) as con:
        con.execute("UPDATE reading_sessions SET draft_fmt = NULL WHERE id = ?", (sid,))
        con.commit()
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 2

    # Formato atual e mesmo digest: reusa, sem chamar o Hermes de novo.
    client.post(f"/reading/sessions/{sid}/draft", json={"pagina_final": 214})
    assert chamadas["n"] == 2
