"""Portado da linha local (revisão Claude x Codex, 11-12/09/2026).

1. Limites de tamanho POR CAMPO nos modelos de entrada (não um middleware global):
   estourar vira 422 genérico, sem eco do conteúdo.
2. Reserva ATÔMICA do slot do dia pro digest e pros nudges: duas chamadas simultâneas
   não entregam em dobro; falha de envio devolve a reserva (retry same-day segue
   permitido); explosão no meio do envio marca `incerto` e ninguém reenvia hoje.
"""
import asyncio
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app import main, notify, store, tasks, telegram
from app.config import settings
from app.main import app

HDR = {"X-Internal-Token": settings.internal_token}


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()


@pytest.fixture
def client(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "app_password", "senha-certa")
    monkeypatch.setattr(settings, "tasks_source", "mock")
    return TestClient(app)


# ---------------------------------------------------------------------------
# limites por campo
# ---------------------------------------------------------------------------

def _auth(client):
    r = client.post("/auth/login", json={"password": "senha-certa"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_captura_acima_do_teto_vira_422_sem_eco(client):
    h = _auth(client)
    texto = "S3GR3D0-" * (main.TEXTO_CAPTURA // 8 + 10)
    r = client.post("/capture", json={"text": texto}, headers=h)
    assert r.status_code == 422
    assert r.json() == {"detail": "entrada inválida", "code": "validation_error"}
    assert "S3GR3D0" not in r.text


def test_captura_no_teto_passa(client, monkeypatch):
    h = _auth(client)
    texto = "a" * main.TEXTO_CAPTURA
    r = client.post("/capture", json={"text": texto}, headers=h)
    assert r.status_code == 200


def test_snapshot_de_leitura_com_chunks_demais_vira_422(client):
    h = _auth(client)
    buffer = [
        {"seq": i + 1, "hook": "texto", "texto": "x"}
        for i in range(main.MAX_CHUNKS_SNAPSHOT + 1)
    ]
    r = client.post(
        "/reading/sessions/1/reconcile",
        json={"client_key": "k", "livro": "L", "buffer": buffer},
        headers=h,
    )
    assert r.status_code == 422


def test_chat_longo_passa_e_turno_gigante_vira_422(client):
    """A tela manda a conversa inteira; o hermes_client corta nos últimos turnos.
    Um teto na LISTA matava conversas longas com 422 (revisão Codex, 12/09/2026)."""
    h = _auth(client)
    historico = [{"role": "user", "text": "oi"}] * 200
    r = client.post("/chat", json={"text": "e aí", "historico": historico}, headers=h)
    assert r.status_code == 200
    gigante = [{"role": "user", "text": "x" * (main.TEXTO_CAPTURA + 1)}]
    r = client.post("/chat", json={"text": "e aí", "historico": gigante}, headers=h)
    assert r.status_code == 422


def test_device_token_vazio_ou_gigante_vira_422(client):
    h = _auth(client)
    assert client.post("/devices", json={"token": ""}, headers=h).status_code == 422
    assert (
        client.post("/devices", json={"token": "T" * (main.TEXTO_CURTO + 1)}, headers=h).status_code
        == 422
    )


def test_notify_interno_com_body_gigante_vira_422(client):
    r = client.post(
        "/internal/notify",
        json={"body": "b" * (main.TEXTO_CAPTURA + 1)},
        headers=HDR,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# reserva atômica (store)
# ---------------------------------------------------------------------------

def test_reserva_so_um_pega(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert store.reservar_notif_dia("digest", "2026-09-12") is True
    assert store.reservar_notif_dia("digest", "2026-09-12") is False
    # outro dia / outro evento não colidem
    assert store.reservar_notif_dia("digest", "2026-09-13") is True
    assert store.reservar_notif_dia("nudge_jornal", "2026-09-12") is True


def test_liberar_devolve_so_reserva_em_curso(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert store.reservar_notif_dia("digest", "d") is True
    store.liberar_reserva_notif("digest", "d")
    assert store.reservar_notif_dia("digest", "d") is True     # voltou a estar livre
    store.concluir_reserva_notif("digest", "d", "entregue")
    store.liberar_reserva_notif("digest", "d")                 # não apaga o que foi entregue
    assert store.reservar_notif_dia("digest", "d") is False


def test_incerto_bloqueia_o_dia(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert store.reservar_notif_dia("digest", "d") is True
    store.concluir_reserva_notif("digest", "d", "incerto")
    assert store.reservar_notif_dia("digest", "d") is False
    assert store.reserva_notif("digest", "d")["estado"] == "incerto"


def test_reserva_em_curso_velha_pode_ser_tomada(tmp_path, monkeypatch):
    """Um processo que morreu com a reserva na mão não cala o digest pelo dia inteiro."""
    _fresh_db(tmp_path, monkeypatch)
    assert store.reservar_notif_dia("digest", "d") is True
    assert store.reservar_notif_dia("digest", "d") is False
    with closing(sqlite3.connect(settings.db_path)) as con:
        con.execute(
            "UPDATE notif_reserva SET ts = ts - ? WHERE evento = 'digest'",
            (store.RESERVA_STALE_S + 1,),
        )
        con.commit()
    assert store.reservar_notif_dia("digest", "d") is True


# ---------------------------------------------------------------------------
# reserva atômica (rotas)
# ---------------------------------------------------------------------------

def _um_item(monkeypatch):
    monkeypatch.setattr(
        tasks, "_open", lambda: [tasks._Task("a", "Pagar boleto", "Finanças", due_offset=-1)]
    )


async def test_duas_chamadas_simultaneas_entregam_uma_vez(client, monkeypatch):
    _um_item(monkeypatch)
    sent = []

    async def fake_send(text):
        await asyncio.sleep(0.05)   # janela grande o bastante pra segunda passar no dedupe
        sent.append(text)
        return True

    monkeypatch.setattr(telegram, "send", fake_send)
    r1, r2 = await asyncio.gather(
        main.internal_run_digest(settings.internal_token),
        main.internal_run_digest(settings.internal_token),
    )
    assert len(sent) == 1
    assert sorted("skipped" in r for r in (r1, r2)) == [False, True]


def test_falha_de_envio_devolve_a_reserva(client, monkeypatch):
    _um_item(monkeypatch)
    respostas = iter([False, True])

    async def fake_send(text):
        return next(respostas)

    monkeypatch.setattr(telegram, "send", fake_send)
    hoje = main.pontos.hoje_local().isoformat()
    assert client.post("/internal/run-digest", headers=HDR).json()["telegram"] is False
    assert store.reserva_notif("digest", hoje) is None            # devolvida
    assert client.post("/internal/run-digest", headers=HDR).json()["telegram"] is True
    assert store.reserva_notif("digest", hoje)["estado"] == "entregue"


def test_explosao_no_envio_marca_incerto_e_nao_reenvia_hoje(client, monkeypatch):
    _um_item(monkeypatch)
    chamadas = []

    async def explode(kind, texto, *, sensivel=False):
        chamadas.append(kind)
        raise RuntimeError("caiu no meio do envio")

    monkeypatch.setattr(notify, "notificar", explode)
    hoje = main.pontos.hoje_local().isoformat()
    with pytest.raises(RuntimeError):
        client.post("/internal/run-digest", headers=HDR)
    assert store.reserva_notif("digest", hoje)["estado"] == "incerto"
    # segunda chamada no mesmo dia: não tenta de novo (pode TER saído)
    r = client.post("/internal/run-digest", headers=HDR)
    assert "skipped" in r.json()
    assert chamadas == ["digest"]


def test_falha_ao_calcular_o_digest_devolve_a_reserva(client, monkeypatch):
    async def run_digest_quebrado():
        raise RuntimeError("ClickUp fora")

    monkeypatch.setattr(tasks, "run_digest", run_digest_quebrado)
    hoje = main.pontos.hoje_local().isoformat()
    with pytest.raises(RuntimeError):
        client.post("/internal/run-digest", headers=HDR)
    assert store.reserva_notif("digest", hoje) is None


async def test_nudge_simultaneo_entrega_uma_vez(client, monkeypatch):
    sent = []

    async def fake_send(text):
        await asyncio.sleep(0.05)
        sent.append(text)
        return True

    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(main.ritos, "atrasado", lambda kind, agora: False)
    body = main.NudgeIn(kind="jornal")
    r1, r2 = await asyncio.gather(
        main.internal_nudge(body, settings.internal_token),
        main.internal_nudge(body, settings.internal_token),
    )
    assert len(sent) == 1
    assert sorted("skipped" in r for r in (r1, r2)) == [False, True]


def test_telegram_incerto_marca_a_reserva_e_nao_reenvia_hoje(client, monkeypatch):
    """ReadTimeout = o request saiu e a resposta não veio: pode TER chegado.
    Antes virava False, a reserva era liberada e o cron seguinte mandava de novo."""
    _um_item(monkeypatch)
    tentativas = []

    async def send_incerto(text):
        tentativas.append(text)
        raise telegram.EntregaIncerta("ReadTimeout")

    monkeypatch.setattr(telegram, "send", send_incerto)
    hoje = main.pontos.hoje_local().isoformat()
    with pytest.raises(telegram.EntregaIncerta):
        client.post("/internal/run-digest", headers=HDR)
    assert store.reserva_notif("digest", hoje)["estado"] == "incerto"
    r = client.post("/internal/run-digest", headers=HDR)
    assert "skipped" in r.json()
    assert len(tentativas) == 1
