"""Ticket da Expo não é entrega — o recibo é.

`_avaliar_push` decide "entregou" lendo o TICKET, e a Expo reporta
`DeviceNotRegistered` majoritariamente no RECIBO (`/getReceipts`), que só existe
minutos depois. Com um token morto devolvendo ticket `ok`: entregou=True → a ponte
do Telegram nunca sobe → o aviso some → e o `notif_log` grava push/entregue=1.

O log mente, e é justamente o log que a gente usaria para descobrir o problema.
Risco real porque `add_device` é INSERT OR REPLACE sem expiração e cada APK novo
gera token novo.
"""
import time

import pytest

from app import notify, push, store
from app.config import settings


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()


def test_envio_guarda_os_tickets_para_conferir_depois():
    store.registrar_tickets([("ticket-1", "ExponentPushToken[vivo]")])

    pendentes = store.tickets_a_conferir(idade_minima_s=0)
    assert [t["ticket_id"] for t in pendentes] == ["ticket-1"]


def test_ticket_recem_enviado_ainda_nao_e_conferido():
    """A Expo leva minutos para publicar o recibo: perguntar cedo demais é ruído."""
    store.registrar_tickets([("ticket-novo", "ExponentPushToken[x]")])

    assert store.tickets_a_conferir(idade_minima_s=900) == []


async def test_recibo_de_device_morto_remove_o_aparelho(monkeypatch):
    store.add_device("ExponentPushToken[morto]")
    store.registrar_tickets([("t1", "ExponentPushToken[morto]")])

    async def fake_receipts(ids):
        return {"t1": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}

    monkeypatch.setattr(push, "get_receipts", fake_receipts)

    await notify.conferir_recibos(idade_minima_s=0)

    assert store.list_devices() == []


async def test_recibo_ok_nao_remove_nada(monkeypatch):
    store.add_device("ExponentPushToken[vivo]")
    store.registrar_tickets([("t2", "ExponentPushToken[vivo]")])

    async def fake_receipts(ids):
        return {"t2": {"status": "ok"}}

    monkeypatch.setattr(push, "get_receipts", fake_receipts)

    await notify.conferir_recibos(idade_minima_s=0)

    assert store.list_devices() == ["ExponentPushToken[vivo]"]
    assert store.tickets_a_conferir(idade_minima_s=0) == []


async def test_expo_fora_do_ar_nao_derruba_nem_perde_o_ticket(monkeypatch):
    store.add_device("ExponentPushToken[vivo]")
    store.registrar_tickets([("t3", "ExponentPushToken[vivo]")])

    async def explode(ids):
        raise RuntimeError("expo fora do ar")

    monkeypatch.setattr(push, "get_receipts", explode)

    await notify.conferir_recibos(idade_minima_s=0)

    assert store.list_devices() == ["ExponentPushToken[vivo]"]
    assert len(store.tickets_a_conferir(idade_minima_s=0)) == 1, "tenta de novo depois"


async def test_envio_real_registra_os_tickets(monkeypatch):
    """O elo que faltava: guardar o recibo não adianta se o envio não registra."""
    store.add_device("ExponentPushToken[abc]")

    async def fake_send(tokens, title, body, data=None):
        return {"sent": 1, "tickets": [{"status": "ok", "id": "ticket-real"}]}

    monkeypatch.setattr(push, "send_push", fake_send)

    await notify.notificar("nudge_toque", "5h30")

    assert [t["ticket_id"] for t in store.tickets_a_conferir(idade_minima_s=0)] == [
        "ticket-real"
    ]
