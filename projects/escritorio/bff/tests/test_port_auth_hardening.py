"""Endurecimentos de auth portados do ramo local de set/2026 (Claude x Codex, 11/09).

Três buracos pequenos, cada um com uma regressão:
  * `_check_internal` comparava com `!=` — tempo variável e, com `INTERNAL_TOKEN`
    vazio no .env, qualquer header vazio passava.
  * `require_auth` aceitava JWT assinado sem `exp` (válido pra sempre) e não
    limitava o tamanho do token antes do decode.
  * O 422 padrão do FastAPI ecoa `input` — no login isso repete a senha malformada.
"""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app import main, store
from app.auth import secret_equal
from app.config import DEFAULTS, settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "internal_token", "itok")
    store.init_db()
    return TestClient(app)


# --- token interno -----------------------------------------------------------

def test_secret_equal_vazio_nunca_passa():
    assert secret_equal("", "") is False
    assert secret_equal(None, "x") is False
    assert secret_equal("x", "") is False
    assert secret_equal("segredo-ção", "segredo-ção") is True
    assert secret_equal("segredo-ção", "segredo-cao") is False


def test_internal_token_vazio_no_env_nao_abre_a_porta(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_token", "")
    r = client.post("/internal/nudge", json={"kind": "closing"}, headers={"X-Internal-Token": ""})
    assert r.status_code == 403


def test_internal_token_errado_e_403_certo_passa(client, monkeypatch):
    errado = client.post("/internal/nudge", json={"kind": "closing"}, headers={"X-Internal-Token": "nope"})
    assert errado.status_code == 403
    certo = client.post("/internal/nudge", json={"kind": "closing"}, headers={"X-Internal-Token": "itok"})
    assert certo.status_code != 403


def test_guard_rejeita_segredo_vazio(monkeypatch):
    for field in DEFAULTS:
        monkeypatch.setattr(settings, field, f"ok-{field}-0123456789")
    monkeypatch.setattr(settings, "internal_token", "")
    with pytest.raises(RuntimeError, match="segredos default detectados"):
        main._guard_default_secrets()


# --- JWT ----------------------------------------------------------------------

def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_jwt_sem_exp_e_recusado(client):
    eterno = jwt.encode({"sub": "owner", "iat": int(time.time())}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/tasks", headers=_hdr(eterno)).status_code == 401


def test_jwt_com_sub_estranho_e_recusado(client):
    now = int(time.time())
    outro = jwt.encode({"sub": "admin", "iat": now, "exp": now + 60}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/tasks", headers=_hdr(outro)).status_code == 401


def test_jwt_gigante_e_recusado_antes_do_decode(client):
    assert client.get("/tasks", headers=_hdr("x" * 9000)).status_code == 401


def test_jwt_emitido_pelo_login_continua_valido(client, monkeypatch):
    monkeypatch.setattr(settings, "app_password", "senha-certa")
    token = client.post("/auth/login", json={"password": "senha-certa"}).json()["token"]
    assert client.get("/tasks", headers=_hdr(token)).status_code == 200


# --- 422 sem eco ---------------------------------------------------------------

def test_422_do_login_nao_ecoa_a_senha(client):
    r = client.post("/auth/login", json={"password": ["senha-vazada-123"]})
    assert r.status_code == 422
    assert "senha-vazada-123" not in r.text
    assert r.json() == {"detail": "entrada inválida", "code": "validation_error"}


# --- guard de boot: placeholders, tamanho e fonte de tarefas (revisão Codex 2026-10-11) ---


def _segredos_bons(monkeypatch):
    for field in DEFAULTS:
        monkeypatch.setattr(settings, field, f"ok-{field}-" + "0123456789abcdef" * 2)


def test_guard_aceita_segredos_fortes(monkeypatch):
    _segredos_bons(monkeypatch)
    main._guard_default_secrets()


def test_guard_rejeita_placeholder_do_env_example(monkeypatch):
    """Achado #1: o JWT_SECRET do `.env.example` não estava em DEFAULTS e passava."""
    _segredos_bons(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret", "troque-por-32-ou-mais-caracteres-aleatorios")
    with pytest.raises(RuntimeError, match="jwt_secret: placeholder"):
        main._guard_default_secrets()


def test_guard_rejeita_jwt_curto(monkeypatch):
    _segredos_bons(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret", "abcdef0123456789")  # 16 < 32
    with pytest.raises(RuntimeError, match="jwt_secret: menos de 32"):
        main._guard_default_secrets()


def test_guard_nao_vaza_o_valor_na_mensagem(monkeypatch):
    _segredos_bons(monkeypatch)
    monkeypatch.setattr(settings, "app_password", "curta")
    with pytest.raises(RuntimeError) as exc:
        main._guard_default_secrets()
    assert "curta" not in str(exc.value)


def test_guard_tasks_source_clickup_sem_token_derruba_o_boot(monkeypatch):
    """Achado #4: clickup sem token caía em silêncio no mock."""
    monkeypatch.setattr(settings, "tasks_source", "clickup")
    monkeypatch.setattr(settings, "clickup_token", "")
    with pytest.raises(RuntimeError, match="CLICKUP_TOKEN"):
        main._guard_tasks_source()


def test_guard_tasks_source_desconhecido(monkeypatch):
    monkeypatch.setattr(settings, "tasks_source", "notion")
    with pytest.raises(RuntimeError, match="desconhecido"):
        main._guard_tasks_source()


def test_guard_tasks_source_aceita_mock_e_clickup_com_token(monkeypatch):
    monkeypatch.setattr(settings, "tasks_source", "mock")
    main._guard_tasks_source()
    monkeypatch.setattr(settings, "tasks_source", "clickup")
    monkeypatch.setattr(settings, "clickup_token", "pk_teste")
    main._guard_tasks_source()
