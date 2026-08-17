"""Camada única de notificação (P2 item 4, metade BFF).

Antes: todo lugar que avisa chamava `telegram.send` direto — 100% dos avisos saíam
por Telegram, embora o Leo tenha pedido push in-app três vezes. `push.py` e
`/internal/notify` existiam e ninguém chamava.

Agora existe UM ponto: `notify.notificar(kind, texto, sensivel=)`.

Invariantes travados aqui:
- push PRIMEIRO (é o canal que o Leo pediu); Telegram é a PONTE — só entra quando o
  push não entregou (sem device, erro, ticket de erro). A SPEC: "Telegram = ponte de
  transição até o push in-app existir";
- o canal REAL usado vai pro `notif_log` — é ele que alimenta o dedupe por dia;
- lei 7: `sensivel=True` → o corpo que vai pro preview (lockscreen) é neutro, em
  QUALQUER canal.
"""
import pytest
from fastapi.testclient import TestClient

from app import main, notify, store
from app.config import settings
from app.main import app


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    return tmp_path


@pytest.fixture
def canais(monkeypatch):
    """Espiona os dois canais sem tocar a rede."""
    enviados = {"push": [], "telegram": []}

    async def fake_push(tokens, title, body, data=None):
        enviados["push"].append({"tokens": tokens, "title": title, "body": body})
        return {"sent": len(tokens), "tickets": [{"status": "ok"} for _ in tokens]}

    async def fake_telegram(text):
        enviados["telegram"].append(text)
        return True

    monkeypatch.setattr(notify.push, "send_push", fake_push)
    monkeypatch.setattr(notify.telegram, "send", fake_telegram)
    return enviados


def _notifs() -> list[tuple]:
    with store._connect() as con:
        rows = con.execute(
            "SELECT evento, canal, entregue FROM notif_log ORDER BY rowid"
        ).fetchall()
    return [(r["evento"], r["canal"], r["entregue"]) for r in rows]


async def test_usa_push_quando_ha_device(db, canais):
    store.add_device("ExponentPushToken[abc]")

    r = await notify.notificar("teste", "corpo do aviso")

    assert r == {"push": True, "telegram": False}
    assert canais["push"] == [
        {
            "tokens": ["ExponentPushToken[abc]"],
            "title": "Escritório",
            "body": "corpo do aviso",
        }
    ]
    assert canais["telegram"] == []                 # push entregou: a ponte não sobe
    assert _notifs() == [("teste", "push", 1)]      # o canal REAL


async def test_cai_pro_telegram_quando_nao_ha_device(db, canais):
    r = await notify.notificar("teste", "corpo do aviso")

    assert r == {"push": False, "telegram": True}
    assert canais["push"] == []                     # sem device: nem tenta
    assert canais["telegram"] == ["corpo do aviso"]
    assert _notifs() == [("teste", "telegram", 1)]


async def test_push_que_falha_cai_pro_telegram(db, canais, monkeypatch):
    store.add_device("ExponentPushToken[abc]")

    async def push_explode(tokens, title, body, data=None):
        raise RuntimeError("expo fora do ar")

    monkeypatch.setattr(notify.push, "send_push", push_explode)

    r = await notify.notificar("teste", "corpo do aviso")

    assert r == {"push": False, "telegram": True}
    assert canais["telegram"] == ["corpo do aviso"]
    assert _notifs() == [("teste", "telegram", 1)]


async def test_ticket_de_erro_do_expo_nao_conta_como_entrega(db, canais, monkeypatch):
    store.add_device("ExponentPushToken[morto]")

    async def push_com_erro(tokens, title, body, data=None):
        return {"sent": 1, "tickets": [{"status": "error", "message": "DeviceNotRegistered"}]}

    monkeypatch.setattr(notify.push, "send_push", push_com_erro)

    r = await notify.notificar("teste", "corpo do aviso")

    assert r == {"push": False, "telegram": True}   # a ponte segura
    assert _notifs() == [("teste", "telegram", 1)]
    assert store.list_devices() == []                 # token morto não é tentado de novo


async def test_fanout_misto_entrega_sem_telegram_e_remove_so_stale(
    db,
    canais,
    monkeypatch,
):
    store.add_device("ExponentPushToken[vivo]")
    store.add_device("ExponentPushToken[morto]")

    async def push_misto(tokens, title, body, data=None):
        assert tokens == ["ExponentPushToken[vivo]", "ExponentPushToken[morto]"]
        return {
            "sent": 2,
            "tickets": [
                {"status": "ok", "id": "ticket-ok"},
                {
                    "status": "error",
                    "message": "token inválido",
                    "details": {"error": "DeviceNotRegistered"},
                },
            ],
        }

    monkeypatch.setattr(notify.push, "send_push", push_misto)

    result = await notify.notificar("fanout", "corpo")

    assert result == {"push": True, "telegram": False}
    assert canais["telegram"] == []
    assert store.list_devices() == ["ExponentPushToken[vivo]"]
    assert _notifs() == [("fanout", "push", 1)]


@pytest.mark.parametrize("tickets", [[], [{"status": "ok"}]])
async def test_tickets_ausentes_ou_incompletos_falham_fechado(
    db,
    canais,
    monkeypatch,
    tickets,
):
    store.add_device("ExponentPushToken[a]")
    store.add_device("ExponentPushToken[b]")

    async def push_sem_receipt_completo(tokens, title, body, data=None):
        return {"sent": len(tokens), "tickets": tickets}

    monkeypatch.setattr(notify.push, "send_push", push_sem_receipt_completo)

    result = await notify.notificar("incerto", "corpo")

    assert result == {"push": False, "telegram": True}
    assert canais["telegram"] == ["corpo"]
    assert store.list_devices() == ["ExponentPushToken[a]", "ExponentPushToken[b]"]


async def test_nenhum_canal_entrega_loga_falha(db, canais, monkeypatch):
    async def telegram_falha(text):
        return False

    monkeypatch.setattr(notify.telegram, "send", telegram_falha)

    r = await notify.notificar("teste", "corpo do aviso")

    assert r == {"push": False, "telegram": False}
    assert _notifs() == [("teste", "telegram", 0)]
    assert store.notif_sent_today("teste") is False   # falha NÃO consome o dia


async def test_telegram_que_explode_nao_propaga(db, canais, monkeypatch):
    async def telegram_explode(text):
        raise RuntimeError("rede caiu")

    monkeypatch.setattr(notify.telegram, "send", telegram_explode)

    r = await notify.notificar("teste", "corpo do aviso")

    assert r == {"push": False, "telegram": False}
    assert _notifs() == [("teste", "telegram", 0)]


async def test_sensivel_nao_vaza_conteudo_em_nenhum_preview(db, canais):
    store.add_device("ExponentPushToken[abc]")

    await notify.notificar("teste", "Marcar psiquiatra às 15h", sensivel=True)
    await notify.notificar("teste2", "Marcar psiquiatra às 15h", sensivel=True)

    corpos = [p["body"] for p in canais["push"]] + canais["telegram"]
    assert corpos and all("psiquiatra" not in c for c in corpos)   # lei 7
    assert all("abre o app" in c for c in corpos)                  # e ainda é acionável


async def test_nao_sensivel_sai_verbatim(db, canais):
    await notify.notificar("teste", "📥 staging: 4 itens — triar no ClickUp")
    assert canais["telegram"] == ["📥 staging: 4 itens — triar no ClickUp"]


# --- fiação: os nudges novos passam pelo notificar ---------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "internal_token", "itok")
    store.init_db()
    return TestClient(app)


@pytest.mark.parametrize(
    "kind,trecho",
    [("toque", "yoga ou dia corrida"), ("checkin", "check-in"), ("shutdown", "Shutdown")],
)
def test_nudges_novos_existem_e_saem_pelo_notificar(client, canais, nudge_no_horario, kind, trecho):
    r = client.post(
        "/internal/nudge",
        json={"kind": kind},
        headers={"X-Internal-Token": "itok"},
    )
    assert r.status_code == 200
    assert r.json()["telegram"] is True
    assert len(canais["telegram"]) == 1 and trecho in canais["telegram"][0]

    with store._connect() as con:
        row = con.execute(
            "SELECT evento, canal FROM notif_log ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
    assert (row["evento"], row["canal"]) == (f"nudge_{kind}", "telegram")


def test_nudge_novo_dedupe_no_mesmo_dia(client, canais, nudge_no_horario):
    hdr = {"X-Internal-Token": "itok"}
    assert client.post("/internal/nudge", json={"kind": "toque"}, headers=hdr).json()["ok"]
    r2 = client.post("/internal/nudge", json={"kind": "toque"}, headers=hdr)
    assert r2.json() == {"skipped": True}
    assert len(canais["telegram"]) == 1


def test_digest_sai_pelo_push_quando_ha_device(client, canais, monkeypatch):
    from app import tasks

    monkeypatch.setattr(settings, "tasks_source", "mock")
    monkeypatch.setattr(tasks, "_open", lambda: [])
    monkeypatch.setattr(tasks, "routine_lines", lambda today=None: ["🔁 academia: 3 furos em 7d."])
    store.add_device("ExponentPushToken[abc]")

    r = client.post("/internal/run-digest", headers={"X-Internal-Token": "itok"})

    assert r.json() == {"count": 0, "telegram": False}   # push entregou; a ponte não subiu
    assert len(canais["push"]) == 1 and "academia" in canais["push"][0]["body"]
    assert canais["telegram"] == []
    assert store.notif_sent_today("digest") is True      # dedupe conta a ENTREGA real


async def test_scheduler_hora_marcada_passa_pelo_notificar(db, canais):
    import time as _t

    store.add_device("ExponentPushToken[abc]")
    store.add_schedule(_t.time() - 5, "minha", "cobrar o Yan (c9)")

    await main.fire_due_schedules()

    assert canais["push"] and canais["push"][0]["body"] == "⏰ cobrar o Yan (c9)"
    assert store.due_schedules(_t.time()) == []           # entregou → marcou disparado
    assert _notifs() == [("hora_marcada", "push", 1)]


def test_internal_notify_usa_camada_unica_com_fallback_e_lei_7(client, canais):
    response = client.post(
        "/internal/notify",
        json={
            "title": "Título que não deve furar a camada",
            "body": "Marcar psiquiatra às 15h",
            "kind": "manual_health",
            "sensivel": True,
        },
        headers={"X-Internal-Token": "itok"},
    )

    assert response.status_code == 200
    assert response.json() == {"push": False, "telegram": True}
    assert len(canais["telegram"]) == 1
    assert "psiquiatra" not in canais["telegram"][0]
    assert "abre o app" in canais["telegram"][0]
    assert _notifs() == [("manual_health", "telegram", 1)]
