"""Pure cadence rules — the heart of Flow B. No I/O, no LLM, fully deterministic,
so it is exhaustively unit-tested (SPEC FR-4/FR-5, SWU-CUT-001/002)."""

from __future__ import annotations

from datetime import date

from .config import CadenceRule
from .models import Task

# Statuses that mean "no longer needs chasing". Compared case-insensitively.
DEFAULT_CLOSED_STATUSES = frozenset(
    {
        "closed", "complete", "completed", "done", "resolved", "cancelled", "canceled",
        "concluído", "concluido", "concluída", "concluida", "cancelado", "cancelada",
        "finalizado", "finalizada", "arquivado",
    }
)

# Tone labels, ordered from calm to urgent.
TONE_NO_PRAZO = "no_prazo"
TONE_LEVE = "leve"
TONE_FIRME = "firme"
TONE_URGENTE = "urgente"

TONE_MARKERS = {
    TONE_NO_PRAZO: "🟡",
    TONE_LEVE: "🟠",
    TONE_FIRME: "🔴",
    TONE_URGENTE: "🚨",
}


def is_closed(status, closed_statuses=DEFAULT_CLOSED_STATUSES) -> bool:
    if not status:
        return False
    return status.strip().lower() in closed_statuses


def needs_nudge(task: Task, rule: CadenceRule, today: date,
                closed_statuses=DEFAULT_CLOSED_STATUSES) -> bool:
    """True if this task should appear in today's digest.

    Chased when ANY branch matches:
      - due soon: due date is today..+vence_em_dias (not yet overdue),
      - overdue: any past-due task (when rule.atrasada),
      - stale: untouched for >= sem_update_dias.
    Closed tasks are never chased.
    """
    if is_closed(task.status, closed_statuses):
        return False

    # overdue
    if rule.atrasada and task.due_date is not None and task.days_overdue(today) > 0:
        return True

    # due soon (today or within N days, not overdue)
    if rule.vence_em_dias is not None and task.due_date is not None:
        until = task.days_until_due(today)
        if until is not None and 0 <= until <= rule.vence_em_dias:
            return True

    # stale (no recent update)
    if rule.sem_update_dias is not None:
        since = task.days_since_update(today)
        if since is not None and since >= rule.sem_update_dias:
            return True

    return False


def tone(days_overdue: int) -> str:
    """Bucketed escalation label from days overdue (0 or negative = on time)."""
    if days_overdue <= 0:
        return TONE_NO_PRAZO
    if days_overdue <= 2:
        return TONE_LEVE
    if days_overdue <= 6:
        return TONE_FIRME
    return TONE_URGENTE


def select(tasks, rule: CadenceRule, today: date,
           closed_statuses=DEFAULT_CLOSED_STATUSES) -> list[Task]:
    """Filter tasks down to those that need chasing today."""
    return [t for t in tasks if needs_nudge(t, rule, today, closed_statuses)]
