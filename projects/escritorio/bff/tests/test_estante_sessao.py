import pytest
from fastapi.testclient import TestClient

from app import store
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
