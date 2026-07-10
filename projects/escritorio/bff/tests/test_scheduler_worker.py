import time

from app import main, store
from app.config import settings


async def test_dispara_vencidos_uma_vez(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    sent = []

    async def fake_send(text):
        sent.append(text)
        return True

    monkeypatch.setattr(main.telegram, "send", fake_send)
    store.add_schedule(
        time.time() - 5,
        "minha",
        "item capturado com hora marcada (c7) — abre o app",
    )

    await main.fire_due_schedules()
    await main.fire_due_schedules()

    assert sent == ["⏰ item capturado com hora marcada (c7) — abre o app"]


async def test_falha_de_entrega_ainda_marca_disparado(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    sent = []
    notifications = []
    original_log_notif = store.log_notif

    async def fake_send(text):
        sent.append(text)
        return False

    def spy_log_notif(evento, canal, entregue):
        notifications.append((evento, canal, entregue))
        original_log_notif(evento, canal, entregue)

    monkeypatch.setattr(main.telegram, "send", fake_send)
    monkeypatch.setattr(main.store, "log_notif", spy_log_notif)
    schedule_id = store.add_schedule(
        time.time() - 5,
        "minha",
        "item capturado com hora marcada (c8) — abre o app",
    )

    await main.fire_due_schedules()
    await main.fire_due_schedules()

    assert sent == ["⏰ item capturado com hora marcada (c8) — abre o app"]
    assert store.due_schedules(time.time()) == []
    assert notifications == [("hora_marcada", "telegram", False)]
    with store._connect() as con:
        fired = con.execute(
            "SELECT disparado FROM scheduler WHERE id = ?",
            (schedule_id,),
        ).fetchone()
    assert fired["disparado"] == 1
