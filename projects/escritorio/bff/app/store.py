"""Persistência local do P1 (sqlite3 síncrono).

Único dono do schema e das conexões. `_connect()` é o helper interno único: toda
conexão nasce em WAL + busy_timeout (worker de captura e endpoints escrevem em
paralelo, então a concorrência é real). `init_db()` aplica o schema inteiro de
forma idempotente e é chamado no startup (main.lifespan).

Higiene (lei 7): `log_event.meta` e `capture_queue.last_error` NUNCA recebem o
conteúdo capturado — só classe/código de erro e metadados sem PII.
"""
import json
import sqlite3
import time
from contextlib import closing
from datetime import date

from .config import settings

# Teto de tentativas da fila de captura. `pending_captures` esconde quem passou
# do teto e `mark_capture(bump_attempts=True)` marca 'failed' ao atingi-lo.
MAX_ATTEMPTS = 5

# Colunas do contrato de fila (Tasks 9/10/12). `status` fica de fora de propósito:
# em `pending_captures` é sempre 'pending', em `failed_captures` sempre 'failed'.
_CAPTURE_COLS = "id, ts, text, profile, attempts, raw_path, clickup_task_id, last_error"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
  token TEXT PRIMARY KEY, created REAL
);
CREATE TABLE IF NOT EXISTS routine_checks (
  data TEXT NOT NULL, rotina TEXT NOT NULL, feito INTEGER NOT NULL,
  template TEXT NOT NULL, PRIMARY KEY (data, rotina)
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, projeto TEXT,
  categoria TEXT, inicio REAL NOT NULL, fim REAL NOT NULL,
  duracao_s INTEGER NOT NULL, paginas INTEGER, livro TEXT
);
CREATE TABLE IF NOT EXISTS telemetry (
  ts REAL NOT NULL, evento TEXT NOT NULL, ref TEXT DEFAULT '', meta_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS notif_log (
  ts REAL NOT NULL, data_local TEXT NOT NULL, evento TEXT NOT NULL,
  canal TEXT NOT NULL, entregue INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS capture_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, text TEXT NOT NULL,
  profile TEXT, status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0, raw_path TEXT, clickup_task_id TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS digest_runs (
  data_local TEXT PRIMARY KEY, body TEXT NOT NULL, count INTEGER NOT NULL,
  delivered INTEGER NOT NULL, ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS scheduler (
  id INTEGER PRIMARY KEY AUTOINCREMENT, quando REAL NOT NULL, tipo TEXT NOT NULL,
  ref TEXT NOT NULL, disparado INTEGER NOT NULL DEFAULT 0
);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(settings.db_path, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def init_db() -> None:
    with closing(_connect()) as con:
        con.executescript(_SCHEMA)
        con.commit()


# --- devices (push tokens) --------------------------------------------------


def add_device(token: str) -> None:
    with closing(_connect()) as con:
        con.execute(
            "INSERT OR REPLACE INTO devices (token, created) VALUES (?, ?)",
            (token, time.time()),
        )
        con.commit()


def list_devices() -> list[str]:
    with closing(_connect()) as con:
        rows = con.execute("SELECT token FROM devices").fetchall()
    return [r[0] for r in rows]


# --- routine_checks ---------------------------------------------------------


def record_checks(data: str, template: str, checks: list[tuple[str, bool]]) -> None:
    with closing(_connect()) as con:
        con.executemany(
            "INSERT OR REPLACE INTO routine_checks (data, rotina, feito, template) "
            "VALUES (?, ?, ?, ?)",
            [(data, rotina, int(feito), template) for rotina, feito in checks],
        )
        con.commit()


def get_checks_since(data_inicio: str) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM routine_checks WHERE data >= ? ORDER BY data, rotina",
            (data_inicio,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- sessions ---------------------------------------------------------------


def add_session(tipo, projeto, categoria, inicio, fim, duracao_s, paginas, livro) -> int:
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT INTO sessions "
            "(tipo, projeto, categoria, inicio, fim, duracao_s, paginas, livro) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tipo, projeto, categoria, inicio, fim, duracao_s, paginas, livro),
        )
        con.commit()
        return int(cur.lastrowid)


def list_sessions_since(ts: float) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM sessions WHERE inicio >= ? ORDER BY inicio",
            (ts,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- telemetry --------------------------------------------------------------


def log_event(evento: str, ref: str = "", meta: dict | None = None) -> None:
    """Registra um evento de telemetria. `meta` NUNCA carrega conteúdo de captura
    (lei 7) — apenas metadados sem PII (contadores, ids, classes de erro)."""
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO telemetry (ts, evento, ref, meta_json) VALUES (?, ?, ?, ?)",
            (time.time(), evento, ref, json.dumps(meta or {})),
        )
        con.commit()


def count_events_since(evento: str, ts: float) -> int:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT COUNT(*) FROM telemetry WHERE evento = ? AND ts >= ?",
            (evento, ts),
        ).fetchone()
    return int(row[0])


# --- notif_log (dedupe por dia) ---------------------------------------------


def log_notif(evento: str, canal: str, entregue: bool) -> None:
    with closing(_connect()) as con:
        con.execute(
            "INSERT INTO notif_log (ts, data_local, evento, canal, entregue) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), date.today().isoformat(), evento, canal, int(entregue)),
        )
        con.commit()


def notif_sent_today(evento: str) -> bool:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT 1 FROM notif_log "
            "WHERE evento = ? AND data_local = ? AND entregue = 1 LIMIT 1",
            (evento, date.today().isoformat()),
        ).fetchone()
    return row is not None


# --- capture_queue (pending -> done | failed; failed nunca é descartado) -----


def enqueue_capture(text: str, profile: str | None) -> int:
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT INTO capture_queue (ts, text, profile) VALUES (?, ?, ?)",
            (time.time(), text, profile),
        )
        con.commit()
        return int(cur.lastrowid)


def pending_captures(max_attempts: int = MAX_ATTEMPTS) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT {_CAPTURE_COLS} FROM capture_queue "
            "WHERE status = 'pending' AND attempts < ? ORDER BY id",
            (max_attempts,),
        ).fetchall()
    return [dict(r) for r in rows]


def failed_captures() -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            f"SELECT {_CAPTURE_COLS} FROM capture_queue "
            "WHERE status = 'failed' ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def mark_capture(
    id,
    *,
    status=None,
    raw_path=None,
    clickup_task_id=None,
    error=None,
    bump_attempts=False,
) -> None:
    """Atualiza um item da fila. `error` é a classe/código do erro sanitizado pelo
    chamador — NUNCA o conteúdo capturado (lei 7), pois vai para `last_error`.

    Auto-failover: se `bump_attempts=True` empurra `attempts` até `MAX_ATTEMPTS` e
    o chamador não forçou um `status`, o item sai da fila ativa como 'failed' — mas
    permanece na tabela (lei 1: failed nunca é descartado, é reapresentado)."""
    with closing(_connect()) as con:
        if bump_attempts and status is None:
            row = con.execute(
                "SELECT attempts FROM capture_queue WHERE id = ?", (id,)
            ).fetchone()
            if row is not None and row["attempts"] + 1 >= MAX_ATTEMPTS:
                status = "failed"
        sets, params = [], []
        if bump_attempts:
            sets.append("attempts = attempts + 1")
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if raw_path is not None:
            sets.append("raw_path = ?")
            params.append(raw_path)
        if clickup_task_id is not None:
            sets.append("clickup_task_id = ?")
            params.append(clickup_task_id)
        if error is not None:
            sets.append("last_error = ?")
            params.append(error)
        if not sets:
            return
        con.execute(
            f"UPDATE capture_queue SET {', '.join(sets)} WHERE id = ?",
            (*params, id),
        )
        con.commit()


def retry_failed_captures() -> int:
    with closing(_connect()) as con:
        cur = con.execute(
            "UPDATE capture_queue SET status = 'pending', attempts = 0 "
            "WHERE status = 'failed'"
        )
        con.commit()
        return cur.rowcount


# --- digest_runs ------------------------------------------------------------


def save_digest_run(data_local: str, body: str, count: int, delivered: bool) -> None:
    with closing(_connect()) as con:
        con.execute(
            "INSERT OR REPLACE INTO digest_runs "
            "(data_local, body, count, delivered, ts) VALUES (?, ?, ?, ?, ?)",
            (data_local, body, int(count), int(delivered), time.time()),
        )
        con.commit()


def get_digest_run(data_local: str) -> dict | None:
    with closing(_connect()) as con:
        row = con.execute(
            "SELECT * FROM digest_runs WHERE data_local = ?", (data_local,)
        ).fetchone()
    return dict(row) if row is not None else None


# --- scheduler (hora marcada) -----------------------------------------------


def add_schedule(quando_ts: float, tipo: str, ref: str) -> int:
    with closing(_connect()) as con:
        cur = con.execute(
            "INSERT INTO scheduler (quando, tipo, ref) VALUES (?, ?, ?)",
            (quando_ts, tipo, ref),
        )
        con.commit()
        return int(cur.lastrowid)


def due_schedules(now_ts: float) -> list[dict]:
    with closing(_connect()) as con:
        rows = con.execute(
            "SELECT * FROM scheduler WHERE disparado = 0 AND quando <= ? "
            "ORDER BY quando, id",
            (now_ts,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_schedule_fired(id: int) -> None:
    with closing(_connect()) as con:
        con.execute("UPDATE scheduler SET disparado = 1 WHERE id = ?", (id,))
        con.commit()
