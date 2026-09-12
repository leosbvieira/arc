"""`client_key` igual com conteúdo diferente é conflito, não retry.

Antes `enqueue_capture` devolvia o id antigo em silêncio: o app achava que o texto
NOVO estava gravado. O retry idempotente (mesma chave, mesmo conteúdo) continua
devolvendo o mesmo id. Portado do ramo local-2026-09 (revisão Claude x Codex, 11/09).
"""
import pytest
from fastapi.testclient import TestClient

from app import store
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "app_password", "senha-certa")
    store.init_db()
    c = TestClient(app)
    token = c.post("/auth/login", json={"password": "senha-certa"}).json()["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    return c


def test_retry_com_mesma_chave_e_mesmo_conteudo_devolve_o_mesmo_id(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "s.db"))
    store.init_db()
    a = store.enqueue_capture("comprar pão", None, "ck-1", sensivel=False)
    b = store.enqueue_capture("comprar pão", None, "ck-1", sensivel=False)
    assert a == b


def test_mesma_chave_com_texto_diferente_e_conflito(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "s.db"))
    store.init_db()
    a = store.enqueue_capture("comprar pão", None, "ck-1")
    with pytest.raises(store.CaptureKeyConflict) as exc:
        store.enqueue_capture("comprar leite", None, "ck-1")
    assert exc.value.existing_id == a
    assert "leite" not in str(exc.value) and "pão" not in str(exc.value)


def test_mesma_chave_com_sensibilidade_diferente_e_conflito(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "s.db"))
    store.init_db()
    store.enqueue_capture("terapia às 15h", None, "ck-2", sensivel=False)
    with pytest.raises(store.CaptureKeyConflict):
        store.enqueue_capture("terapia às 15h", None, "ck-2", sensivel=True)


def test_rota_capture_responde_409_sem_ecoar_textos(client):
    ok = client.post("/capture", json={"text": "comprar pão", "client_key": "ck-3"})
    assert ok.status_code == 200
    again = client.post("/capture", json={"text": "comprar pão", "client_key": "ck-3"})
    assert again.status_code == 200
    conflito = client.post("/capture", json={"text": "comprar leite", "client_key": "ck-3"})
    assert conflito.status_code == 409
    assert conflito.json()["detail"] == "client_key_conflito"
    assert "leite" not in conflito.text and "pão" not in conflito.text
    # Só UMA linha na fila: o conflito não gravou nada.
    assert len(store.pending_captures()) == 1
