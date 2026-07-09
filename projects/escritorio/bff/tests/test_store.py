import time
from app import store
from app.config import settings


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()


def test_wal_ligado(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    with store._connect() as con:
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_checks_roundtrip(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    store.record_checks("2026-07-09", "yoga", [("yoga", True), ("academia", False)])
    rows = store.get_checks_since("2026-07-01")
    assert {(r["rotina"], r["feito"]) for r in rows} == {("yoga", 1), ("academia", 0)}


def test_checks_reaprovar_substitui(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    store.record_checks("2026-07-09", "yoga", [("yoga", False)])
    store.record_checks("2026-07-09", "yoga", [("yoga", True)])
    rows = store.get_checks_since("2026-07-09")
    assert len(rows) == 1 and rows[0]["feito"] == 1


def test_capture_queue_fluxo(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    cid = store.enqueue_capture("pagar condominio", None)
    assert [p["id"] for p in store.pending_captures()] == [cid]
    store.mark_capture(cid, raw_path="1- Inbox/Raw/x.md")
    assert store.pending_captures()[0]["raw_path"] == "1- Inbox/Raw/x.md"
    store.mark_capture(cid, status="done")
    assert store.pending_captures() == []


def test_capture_vira_failed_e_reapresenta(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    cid = store.enqueue_capture("x", None)
    for _ in range(5):
        store.mark_capture(cid, bump_attempts=True, error="HermesTimeout")
    assert store.pending_captures() == []            # sai da fila ativa...
    failed = store.failed_captures()                 # ...mas NUNCA some (lei 1)
    assert [f["id"] for f in failed] == [cid]
    assert store.retry_failed_captures() == 1        # reapresentacao: volta pra fila
    assert [p["id"] for p in store.pending_captures()] == [cid]


def test_notif_dedupe_por_dia(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert store.notif_sent_today("digest") is False
    store.log_notif("digest", "telegram", True)
    assert store.notif_sent_today("digest") is True


def test_digest_run_persistido(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    store.save_digest_run("2026-07-09", "corpo do digest", 3, True)
    run = store.get_digest_run("2026-07-09")
    assert run["body"] == "corpo do digest" and run["count"] == 3 and run["delivered"] == 1
    assert store.get_digest_run("2026-07-08") is None


def test_scheduler(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    now = time.time()
    sid = store.add_schedule(now - 60, "minha", "entregar relatorio 14h")
    assert [d["id"] for d in store.due_schedules(now)] == [sid]
    store.mark_schedule_fired(sid)
    assert store.due_schedules(now) == []


def test_sessions(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    t0 = time.time()
    store.add_session("leitura", "Antifragil", "leitura", t0 - 1800, t0, 1800, 20, "Antifragil")
    assert store.list_sessions_since(t0 - 86400)[0]["duracao_s"] == 1800
