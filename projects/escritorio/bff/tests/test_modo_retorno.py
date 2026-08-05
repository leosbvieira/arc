"""Modo Retorno: quem some 7+ dias não pode voltar para uma pilha de culpa.

Lei 4 — "dia quebrado = replanejar, não envergonhar". Hoje quem volta de 10 dias
recebe o digest inteiro em 🚨 e o rito da hora como se nada tivesse acontecido.
Para um sistema desenhado para TDAH, é a diferença entre voltar e desinstalar.
"""
import time

import pytest
from fastapi.testclient import TestClient

from app import store
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


def _evento_ha(dias: float, evento: str = "capture_enqueued") -> None:
    with store._connect() as con:
        con.execute(
            "INSERT INTO telemetry (ts, evento, ref, meta_json) VALUES (?, ?, '', '{}')",
            (time.time() - dias * 86400, evento),
        )
        con.commit()


def test_ausencia_longa_e_reportada(client):
    _evento_ha(10)
    assert client.get("/abertura").json()["dias_ausente"] == 10


def test_uso_recente_nao_e_ausencia(client):
    _evento_ha(10)
    _evento_ha(0.2)          # ele usou hoje: vale a interação MAIS RECENTE
    assert client.get("/abertura").json()["dias_ausente"] == 0


def test_sem_historico_nenhum_nao_inventa_ausencia(client):
    """Primeiro uso não é retorno — seria receber "bem-vindo de volta" na estreia."""
    assert client.get("/abertura").json()["dias_ausente"] == 0
