"""Shutdown das 19h (A2) — P2 item 5.

São DOIS ritos diferentes ("A2.3. Sim, sao 2 ritos diferentes."): o Shutdown das 19h
encerra o TRABALHO (pendências, follow-ups, staging: N, as 3 prioridades de amanhã);
o fechamento das 21h é o diário + as rotinas. Este arquivo é só o primeiro.

O ponto de junção: as prioridades salvas no Shutdown de hoje são o que o `GET /abertura`
de AMANHÃ mostra em `prioridades_de_ontem`. É assim que o dia seguinte já nasce planejado.
"""
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import clickup_client, store, tasks
from app.config import settings
from app.main import app, require_auth

HOJE = date.today()
AMANHA = (HOJE + timedelta(days=1)).isoformat()
DIA_MS = 86_400_000


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "tasks_source", "mock")
    store.init_db()
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _ck(id, name, area, *, tags=None, criada_ha_dias=0, due_ms=None) -> dict:
    agora_ms = int(time.time() * 1000)
    return {
        "id": id,
        "name": name,
        "_area": area,
        "status": {"status": "open", "type": "custom"},
        "assignees": [],
        "due_date": due_ms,
        "date_created": str(agora_ms - criada_ha_dias * DIA_MS),
        "tags": [{"name": t} for t in (tags or [])],
    }


@pytest.fixture
def clickup(monkeypatch):
    """Fonte ClickUp fakeada: Trabalho aberto + 1 cobrança 'aguardando' + Staging velho."""
    raw = [
        _ck("w1", "Fechar a proposta", "Trabalho"),
        _ck("w2", "Revisar contrato", "Trabalho"),
        _ck("c1", "Cobrar: Yan", "Staging", tags=["aguardando"], criada_ha_dias=2),
        _ck("s1", "ideia solta", "Staging", criada_ha_dias=9),
        _ck("s2", "outra ideia", "Staging", criada_ha_dias=1),
        _ck("f1", "Pagar boleto", "Finance"),
    ]

    async def fake_fetch_open():
        return raw

    monkeypatch.setattr(tasks, "_use_clickup", lambda: True)
    monkeypatch.setattr(clickup_client, "fetch_open", fake_fetch_open)
    return raw


# --- GET /shutdown -----------------------------------------------------------


def test_shutdown_traz_trabalho_aberto(client, clickup):
    pack = client.get("/shutdown").json()
    assert [t["name"] for t in pack["trabalho_aberto"]] == [
        "Fechar a proposta", "Revisar contrato",
    ]
    assert "Pagar boleto" not in [t["name"] for t in pack["trabalho_aberto"]]


def test_shutdown_traz_follow_ups_da_tag_aguardando(client, clickup):
    follow = client.get("/shutdown").json()["follow_ups"]
    assert [f["name"] for f in follow] == ["Cobrar: Yan"]
    assert follow[0]["origem"] == "clickup"


def test_shutdown_traz_follow_ups_do_scheduler_ainda_nao_disparados(client, clickup):
    pendente = store.add_schedule(time.time() + 3600, "cobrar-terceiro", "cobrar o Yan (c9)")
    disparado = store.add_schedule(time.time() - 60, "minha", "já foi (c8)")
    store.mark_schedule_fired(disparado)

    follow = client.get("/shutdown").json()["follow_ups"]
    nomes = [f["name"] for f in follow]
    assert "cobrar o Yan (c9)" in nomes
    assert "já foi (c8)" not in nomes            # disparado não é follow-up
    sched = next(f for f in follow if f["name"] == "cobrar o Yan (c9)")
    assert sched["origem"] == "scheduler" and sched["id"] == f"sched-{pendente}"


def test_shutdown_devolve_staging_como_DADO_nao_texto(client, clickup):
    """`tasks.staging_line` devolve a linha do digest; aqui o app precisa do NÚMERO."""
    assert client.get("/shutdown").json()["staging"] == {"n": 3, "mais_velho_d": 9}


def test_shutdown_sem_clickup_degrada_para_zero(client):
    pack = client.get("/shutdown").json()
    assert pack["staging"] == {"n": 0, "mais_velho_d": None}
    assert pack["feito"] is False and pack["prioridades"] == []


def test_shutdown_exige_auth():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/shutdown").status_code == 401


# --- POST /shutdown ----------------------------------------------------------


def test_post_salva_as_prioridades_de_amanha(client):
    r = client.post("/shutdown", json={"prioridades": ["a", "b", "c"]})
    assert r.status_code == 200

    pack = client.get("/shutdown").json()
    assert pack["prioridades"] == ["a", "b", "c"]
    assert pack["feito"] is True
    assert store.get_shutdown(HOJE.isoformat())["feito_em"] > 0


def test_post_valida_maximo_de_3_prioridades(client):
    r = client.post("/shutdown", json={"prioridades": ["a", "b", "c", "d"]})
    assert r.status_code == 422
    assert store.get_shutdown(HOJE.isoformat()) is None    # não gravou nada


def test_post_aceita_menos_de_3_e_descarta_vazias(client):
    client.post("/shutdown", json={"prioridades": ["a", "   ", "b"]})
    assert client.get("/shutdown").json()["prioridades"] == ["a", "b"]


def test_post_e_idempotente_regrava(client):
    client.post("/shutdown", json={"prioridades": ["a"]})
    client.post("/shutdown", json={"prioridades": ["x", "y"]})
    assert client.get("/shutdown").json()["prioridades"] == ["x", "y"]


def test_post_exige_auth():
    app.dependency_overrides.clear()
    r = TestClient(app).post("/shutdown", json={"prioridades": []})
    assert r.status_code == 401


# --- a junção: o Shutdown de hoje é a abertura de amanhã ----------------------


def test_prioridades_de_hoje_aparecem_na_abertura_de_amanha(client):
    client.post("/shutdown", json={"prioridades": ["fechar a proposta", "cobrar o Yan"]})

    pack = client.get("/abertura", params={"data": AMANHA}).json()
    assert pack["prioridades_de_ontem"] == ["fechar a proposta", "cobrar o Yan"]


def test_sem_shutdown_ontem_a_abertura_traz_lista_vazia(client):
    pack = client.get("/abertura", params={"data": AMANHA}).json()
    assert pack["prioridades_de_ontem"] == []
