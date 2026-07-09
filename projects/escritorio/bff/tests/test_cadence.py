"""Cadence rules ported from cutuca (SPEC FR-4/FR-5) — pure, deterministic, offline.

Source: projects/cutuca/tests/test_cadence.py, plus the two digest-format cases
from test_nudge.py (format_digest was vendored into app.cadence alongside the rules).

The vendored app.cadence consumes a duck-typed task with PRE-COMPUTED day counts and
no `today` argument, so the original due_date/last_update inputs are translated once,
inside `mk`, into days_overdue / days_until_due / days_since_update. The chase/tone
semantics are unchanged from the validated cutuca suite.
"""

from dataclasses import dataclass
from typing import Optional

from app.cadence import Rule, format_digest, needs_nudge, select, tone


@dataclass
class FakeTask:
    """Minimal task exposing only the attributes app.cadence reads."""

    id: str = "1"
    name: str = "t"
    assignee: Optional[str] = "joão"
    status: Optional[str] = "open"
    days_overdue: int = 0
    days_until_due: Optional[int] = None
    days_since_update: Optional[int] = None


def mk(*, due_in: Optional[int] = None, updated_days_ago: Optional[int] = None, **kw) -> FakeTask:
    """Build a task like the ones app.cadence consumes.

    due_in: days until the due date (0 = today, negative = overdue); None = no due date.
    updated_days_ago: days since the last update; None = never updated / unknown.
    Mirrors cutuca's mk(due_date=TODAY + due_in, last_update=TODAY - updated_days_ago).
    """
    return FakeTask(
        days_until_due=due_in,
        days_overdue=(-due_in if due_in is not None else 0),
        days_since_update=updated_days_ago,
        **kw,
    )


def test_due_today_is_nudged():
    rule = Rule(vence_em_dias=0, atrasada=True, sem_update_dias=None)
    assert needs_nudge(mk(due_in=0), rule) is True


def test_due_within_window_is_nudged():
    rule = Rule(vence_em_dias=2, atrasada=True, sem_update_dias=None)
    assert needs_nudge(mk(due_in=2), rule) is True
    assert needs_nudge(mk(due_in=3), rule) is False


def test_overdue_is_nudged_when_atrasada():
    rule = Rule(vence_em_dias=0, atrasada=True, sem_update_dias=None)
    assert needs_nudge(mk(due_in=-5), rule) is True


def test_overdue_ignored_when_atrasada_false():
    rule = Rule(vence_em_dias=0, atrasada=False, sem_update_dias=None)
    assert needs_nudge(mk(due_in=-5), rule) is False


def test_stale_is_nudged():
    rule = Rule(vence_em_dias=None, atrasada=False, sem_update_dias=3)
    assert needs_nudge(mk(updated_days_ago=3), rule) is True
    assert needs_nudge(mk(updated_days_ago=2), rule) is False


def test_closed_never_nudged():
    rule = Rule(vence_em_dias=0, atrasada=True, sem_update_dias=3)
    assert needs_nudge(mk(due_in=-10, status="complete"), rule) is False
    assert needs_nudge(mk(due_in=-10, status="Concluído"), rule) is False


def test_nothing_matches():
    rule = Rule(vence_em_dias=0, atrasada=True, sem_update_dias=3)
    fine = mk(due_in=10, updated_days_ago=0)
    assert needs_nudge(fine, rule) is False


def test_tone_buckets():
    assert tone(0) == "no_prazo"
    assert tone(-3) == "no_prazo"
    assert tone(1) == "leve"
    assert tone(2) == "leve"
    assert tone(3) == "firme"
    assert tone(6) == "firme"
    assert tone(7) == "urgente"
    assert tone(30) == "urgente"


def test_select_filters():
    rule = Rule(vence_em_dias=0, atrasada=True, sem_update_dias=None)
    tasks = [
        mk(id="a", due_in=0),                  # due today -> in
        mk(id="b", due_in=-1),                 # overdue -> in
        mk(id="c", due_in=5),                  # future -> out
        mk(id="d", due_in=0, status="done"),   # closed -> out
    ]
    got = {t.id for t in select(tasks, rule)}
    assert got == {"a", "b"}


def test_format_digest_orders_most_overdue_first():
    tasks = [
        mk(name="task a", due_in=0),    # due today
        mk(name="task b", due_in=-8),   # 8d overdue
        mk(name="task c", due_in=-2),   # 2d overdue
    ]
    lines = format_digest(tasks, escala_tom=True).splitlines()[1:]  # drop header
    assert "task b" in lines[0]  # most overdue first
    assert "task c" in lines[1]
    assert "task a" in lines[2]  # due today last


def test_format_digest_shows_urgent_marker():
    task = mk(name="task b", due_in=-8)  # 8d overdue -> urgente
    assert "🚨" in format_digest([task], escala_tom=True)
