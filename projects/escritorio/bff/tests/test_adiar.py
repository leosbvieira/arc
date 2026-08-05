"""Adiar é o que a lei 4 exige: replanejar, não envergonhar.

O buraco que isto fecha: não existia PATCH /tasks/{id}. As únicas ações eram
concluir e abrir no ClickUp, então uma tarefa atrasada que o Leo decidiu fazer
semana que vem tinha três saídas — concluir mentindo (polui pontos e review), sair
do app (o "cemitério" que a lei 5 proíbe), ou aguentar 🚨 todo dia. A terceira é a
que treina a ignorar o digest, e aí o produto morre em silêncio.
"""
import pytest
from fastapi.testclient import TestClient

from app import store, tasks
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


@pytest.fixture(autouse=True)
def _uma_atrasada(monkeypatch):
    atrasada = tasks._Task("t1", "Renovar seguro", "Finance", due_offset=-8)
    monkeypatch.setattr(tasks, "_MOCK", [atrasada])
    return atrasada


def test_adiar_move_o_prazo_e_zera_o_atraso(client):
    r = client.patch("/tasks/t1", json={"due": "2030-01-15"})

    assert r.status_code == 200
    assert r.json()["days_overdue"] < 0, "deixou de estar atrasada"


def test_adiar_recusa_data_ambigua(client):
    """Mesmo fail-closed do create: data ambígua não pode remarcar cobrança."""
    assert client.patch("/tasks/t1", json={"due": "15/01/2030"}).status_code == 422
    assert client.patch("/tasks/t1", json={"due": "2030-13-40"}).status_code == 422


def test_adiar_tarefa_inexistente_da_404(client):
    assert client.patch("/tasks/naoexiste", json={"due": "2030-01-15"}).status_code == 404


def test_adiar_registra_telemetria(client):
    """Adiar demais é sinal: sem o evento, ninguém pode cobrar o padrão depois."""
    client.patch("/tasks/t1", json={"due": "2030-01-15"})

    with store._connect() as con:
        eventos = [r[0] for r in con.execute("select evento from telemetry")]
    assert "task_adiada" in eventos
