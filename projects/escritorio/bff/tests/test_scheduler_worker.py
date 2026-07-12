import time

from app import main, store, telegram
from app.config import settings


async def test_dispara_vencidos_uma_vez(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    sent = []

    async def fake_send(text):
        sent.append(text)
        return True

    monkeypatch.setattr(telegram, "send", fake_send)
    store.add_schedule(
        time.time() - 5,
        "minha",
        "item capturado com hora marcada (c7) — abre o app",
    )

    await main.fire_due_schedules()
    await main.fire_due_schedules()

    assert sent == ["⏰ item capturado com hora marcada (c7) — abre o app"]


async def test_falha_de_entrega_permanece_due_ate_retry_ok(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    sent = []
    notifications = []
    marked = []
    outcomes = iter([False, True])
    original_log_notif = store.log_notif
    original_mark = store.mark_schedule_fired

    async def fake_send(text):
        sent.append(text)
        return next(outcomes)

    def spy_log_notif(evento, canal, entregue):
        notifications.append((evento, canal, entregue))
        original_log_notif(evento, canal, entregue)

    def spy_mark(schedule_id):
        marked.append(schedule_id)
        original_mark(schedule_id)

    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(main.store, "log_notif", spy_log_notif)
    monkeypatch.setattr(main.store, "mark_schedule_fired", spy_mark)
    schedule_id = store.add_schedule(
        time.time() - 5,
        "minha",
        "item capturado com hora marcada (c8) — abre o app",
    )

    await main.fire_due_schedules()

    assert [item["id"] for item in store.due_schedules(time.time())] == [
        schedule_id,
    ]

    await main.fire_due_schedules()

    assert sent == [
        "⏰ item capturado com hora marcada (c8) — abre o app",
        "⏰ item capturado com hora marcada (c8) — abre o app",
    ]
    assert store.due_schedules(time.time()) == []
    assert notifications == [
        ("hora_marcada", "telegram", False),
        ("hora_marcada", "telegram", True),
    ]
    assert marked == [schedule_id]

    with store._connect() as con:
        fired = con.execute(
            "SELECT disparado FROM scheduler WHERE id = ?",
            (schedule_id,),
        ).fetchone()
    assert fired["disparado"] == 1


async def test_item_ruim_nao_aborta_os_demais_do_tick(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    notifications = []
    calls = 0

    first_id = store.add_schedule(time.time() - 5, "minha", "primeiro item")
    second_id = store.add_schedule(time.time() - 4, "minha", "segundo item")

    async def fake_send(text):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("falha sintética")
        return True

    def fake_log_notif(evento, canal, entregue):
        notifications.append((evento, canal, entregue))

    monkeypatch.setattr(telegram, "send", fake_send)
    monkeypatch.setattr(main.store, "log_notif", fake_log_notif)

    await main.fire_due_schedules()

    assert calls == 2
    assert notifications == [
        ("hora_marcada", "telegram", False),
        ("hora_marcada", "telegram", True),
    ]
    assert [item["id"] for item in store.due_schedules(time.time())] == [
        first_id,
    ]
    assert second_id not in {
        item["id"] for item in store.due_schedules(time.time())
    }
