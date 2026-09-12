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


def test_init_db_migra_client_key_idempotentemente(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    store.init_db()
    with store._connect() as con:
        columns = {
            row["name"] for row in con.execute("PRAGMA table_info(capture_queue)")
        }
        indexes = {
            row["name"] for row in con.execute("PRAGMA index_list(capture_queue)")
        }
    assert "client_key" in columns
    assert "idx_capture_client_key" in indexes


def test_checks_roundtrip(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    store.record_checks(
        "2026-07-09",
        "yoga",
        [("yoga", True), ("academia", False)],
    )
    rows = store.get_checks_since("2026-07-01")
    assert {(r["rotina"], r["feito"]) for r in rows} == {
        ("yoga", 1),
        ("academia", 0),
    }


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
    assert store.claim_capture(cid) is True
    store.mark_capture(cid, raw_path="1- Inbox/Raw/x.md")
    store.mark_capture(cid, status="done")
    assert store.pending_captures() == []
    with store._connect() as con:
        row = con.execute(
            "SELECT text, status FROM capture_queue WHERE id = ?",
            (cid,),
        ).fetchone()
    assert dict(row) == {"text": "", "status": "done"}


def test_capture_claim_atomico_e_recover(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    cid = store.enqueue_capture("x", None)

    assert store.claim_capture(cid) is True
    assert store.claim_capture(cid) is False
    assert store.pending_captures() == []

    assert store.recover_processing() == 1
    assert [p["id"] for p in store.pending_captures()] == [cid]
    assert store.recover_processing() == 0


def _vencer_backoff(cid: int) -> None:
    """A falha agenda a próxima tentativa (backoff). Aqui a gente adianta o relógio
    para observar a escada de tentativas sem esperar minutos de verdade."""
    import time as _t

    with store._connect() as con:
        con.execute(
            "UPDATE capture_queue SET proxima_em = ? WHERE id = ?", (_t.time() - 1, cid)
        )
        con.commit()


def test_capture_vira_failed_e_reapresenta(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    cid = store.enqueue_capture("x", None)
    for attempt in range(5):
        assert store.claim_capture(cid) is True
        store.mark_capture(cid, bump_attempts=True, error="HermesTimeout")
        if attempt < 4:
            assert store.pending_captures() == [], "espera o backoff antes de retentar"
            _vencer_backoff(cid)
            row = store.pending_captures()[0]
            assert row["attempts"] == attempt + 1

    assert store.pending_captures() == []
    failed = store.failed_captures()
    assert [f["id"] for f in failed] == [cid]
    assert failed[0]["text"] == "x"
    assert store.retry_failed_captures() == 1
    assert [p["id"] for p in store.pending_captures()] == [cid]


def test_capture_client_key_retorna_mesmo_id(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    first = store.enqueue_capture("primeiro texto", None, "device-123")
    # Retry = MESMO conteúdo com a mesma chave (o profile não entra na identidade).
    # Chave igual com texto diferente virou conflito em 12/09/2026 — ver
    # test_port_capture_durable.py.
    second = store.enqueue_capture("primeiro texto", "Capturas", "device-123")

    assert second == first
    with store._connect() as con:
        rows = con.execute(
            "SELECT id, text, client_key FROM capture_queue"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == first
    assert rows[0]["text"] == "primeiro texto"
    assert rows[0]["client_key"] == "device-123"


def test_capture_sem_client_key_permite_multiplos_null(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    first = store.enqueue_capture("a", None)
    second = store.enqueue_capture("b", None)
    assert first != second


def test_notif_dedupe_por_dia(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert store.notif_sent_today("digest") is False
    store.log_notif("digest", "telegram", True)
    assert store.notif_sent_today("digest") is True


def test_digest_run_persistido(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    store.save_digest_run("2026-07-09", "corpo do digest", 3, True)
    run = store.get_digest_run("2026-07-09")
    assert run["body"] == "corpo do digest"
    assert run["count"] == 3
    assert run["delivered"] == 1
    assert store.get_digest_run("2026-07-08") is None


def test_scheduler(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    now = time.time()
    sid = store.add_schedule(now - 60, "minha", "entregar relatorio (c42)")
    assert store.has_schedule_ref("(c42)") is True
    assert store.has_schedule_ref("(c99)") is False
    assert [d["id"] for d in store.due_schedules(now)] == [sid]
    store.mark_schedule_fired(sid)
    assert store.due_schedules(now) == []


def test_sessions(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    t0 = time.time()
    store.add_session(
        "leitura",
        "Antifragil",
        "leitura",
        t0 - 1800,
        t0,
        1800,
        20,
        "Antifragil",
    )
    assert store.list_sessions_since(t0 - 86400)[0]["duracao_s"] == 1800
