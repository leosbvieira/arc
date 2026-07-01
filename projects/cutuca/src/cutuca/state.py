"""SQLite dedupe store for nudges. Key = (task_id, day). Idempotent by construction,
so re-running the digest on the same day never double-nudges (SPEC NFR-3, SWU-CUT-003)."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Union

DayLike = Union[str, date]


def _day_str(day: DayLike) -> str:
    return day.isoformat() if isinstance(day, date) else str(day)


class NudgeState:
    def __init__(self, path: str = "cutuca_state.db"):
        # check_same_thread=False so the APScheduler thread can share the handle.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nudges (
                task_id TEXT NOT NULL,
                day     TEXT NOT NULL,
                ts      TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (task_id, day)
            )
            """
        )
        self._conn.commit()

    def already_nudged(self, task_id: str, day: DayLike) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM nudges WHERE task_id = ? AND day = ? LIMIT 1",
            (str(task_id), _day_str(day)),
        )
        return cur.fetchone() is not None

    def mark_nudged(self, task_id: str, day: DayLike) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO nudges (task_id, day) VALUES (?, ?)",
            (str(task_id), _day_str(day)),
        )
        self._conn.commit()

    def filter_new(self, task_ids, day: DayLike) -> list[str]:
        """Return only the ids not yet nudged on ``day`` (order preserved)."""
        return [tid for tid in task_ids if not self.already_nudged(tid, day)]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "NudgeState":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
