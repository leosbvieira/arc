import sqlite3
import time
from contextlib import contextmanager

from .config import settings


@contextmanager
def _conn():
    conn = sqlite3.connect(settings.db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure(c: sqlite3.Connection) -> None:
    c.execute(
        "CREATE TABLE IF NOT EXISTS devices "
        "(token TEXT PRIMARY KEY, created REAL)"
    )


def init_db() -> None:
    with _conn() as c:
        _ensure(c)


def add_device(token: str) -> None:
    with _conn() as c:
        _ensure(c)
        c.execute(
            "INSERT OR REPLACE INTO devices (token, created) VALUES (?, ?)",
            (token, time.time()),
        )


def list_devices() -> list[str]:
    with _conn() as c:
        _ensure(c)
        rows = c.execute("SELECT token FROM devices").fetchall()
    return [r[0] for r in rows]
