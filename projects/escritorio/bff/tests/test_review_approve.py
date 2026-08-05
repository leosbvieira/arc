"""A Revisão precisa virar artefato — hoje ela é um dashboard e some.

A SPEC A4 pede que o review semanal seja aprovado e gravado em
`Fechamentos/Weekly/YYYY-WW.md`. Sem isso, e sem uma tabela que registre que o
review aconteceu, "2 semanas puladas → Mentor" é matematicamente impossível: o
sistema não tem como saber. Reflexão que não persiste não vira memória.
"""
import pytest
from fastapi.testclient import TestClient

from app import main, store
from app.config import settings
from app.main import app, require_auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def vault(monkeypatch):
    escritos: list[tuple[str, str]] = []

    async def fake_append(path, block, message, header_if_new="", dedupe_marker=None):
        escritos.append((path, block))
        return path

    monkeypatch.setattr(main.vault_client, "append_file", fake_append)
    return escritos


def test_aprovar_grava_o_review_no_vault(client, vault):
    r = client.post("/review/weekly/approve", json={"semana": "2026-W32"})

    assert r.status_code == 200
    assert vault, "nada foi escrito no vault"
    caminho, bloco = vault[0]
    assert caminho == "Fechamentos/Weekly/2026-W32.md"
    assert bloco.strip(), "o bloco não pode ir vazio"


def test_aprovar_registra_que_aconteceu(client, vault):
    """É esta linha que torna 'review pulado' uma pergunta respondível."""
    client.post("/review/weekly/approve", json={"semana": "2026-W32"})

    assert store.review_feito("2026-W32") is True
    assert store.review_feito("2026-W31") is False


def test_aprovar_duas_vezes_nao_duplica(client, vault):
    client.post("/review/weekly/approve", json={"semana": "2026-W32"})
    r = client.post("/review/weekly/approve", json={"semana": "2026-W32"})

    assert r.status_code == 200
    assert store.review_feito("2026-W32") is True


def test_semana_invalida_e_recusada(client, vault):
    assert client.post("/review/weekly/approve", json={"semana": "32/2026"}).status_code == 422
    assert not vault


async def test_mentor_sabe_do_review_pulado(client, vault, monkeypatch):
    """O elo final: sem isto, o "Mentor com voz" da SPEC continua mudo."""
    from app import mentor_contexto, tasks

    monkeypatch.setattr(tasks, "_open", lambda: [])

    texto = await mentor_contexto.montar()
    assert "review" in texto.lower()
