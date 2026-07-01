"""Flow B orchestration: read ClickUp -> cadence select -> dedupe -> format -> send.
Pure code, NO LLM (SPEC §3). All collaborators injectable, so the whole digest is
unit-tested (including two-runs-same-day dedupe, SWU-CUT-005) without a network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from . import cadence
from .config import Config
from .logging_setup import get_logger, log_event
from .models import Task
from .timeutil import get_tz, today_in

log = get_logger("cutuca.nudge")


@dataclass
class DigestResult:
    sent: bool
    count: int
    tasks: list[Task] = field(default_factory=list)
    text: str = ""


def _task_line(task: Task, today: date, escala_tom: bool) -> str:
    overdue = task.days_overdue(today)
    until = task.days_until_due(today)
    assignee = ", ".join(task.assignees) if task.assignees else "sem responsável"

    if overdue > 0:
        when = f"atrasada {overdue}d"
    elif until == 0:
        when = "vence hoje"
    elif until is not None and until > 0:
        when = f"vence em {until}d"
    else:
        since = task.days_since_update(today)
        when = f"parada há {since}d" if since is not None else "sem update"

    marker = ""
    if escala_tom:
        label = cadence.tone(overdue)
        marker = cadence.TONE_MARKERS.get(label, "") + " "
    return f"{marker}{task.name} — {assignee} · {when}"


def format_digest(tasks: list[Task], today: date, *, escala_tom: bool = True) -> str:
    header = f"🔔 Cobranças de hoje ({len(tasks)}):"
    # firmest first: most overdue at the top
    ordered = sorted(tasks, key=lambda t: t.days_overdue(today), reverse=True)
    lines = [_task_line(t, today, escala_tom) for t in ordered]
    return "\n".join([header, *lines])


def run_digest(
    *,
    clickup,
    channel,
    state,
    config: Config,
    today: Optional[date] = None,
) -> DigestResult:
    tz = get_tz(config.timezone)
    today = today or today_in(tz)

    try:
        tasks = clickup.list_tasks(config.clickup.list_id)
    except Exception as exc:
        log_event(log, "digest_read_failed", level=40, error=str(exc))
        return DigestResult(sent=False, count=0)

    selected = cadence.select(tasks, config.cobrar_se, today)
    fresh = [t for t in selected if not state.already_nudged(t.id, today)]

    if not fresh:
        log_event(log, "digest_nothing_new", selected=len(selected))
        return DigestResult(sent=False, count=0)

    text = format_digest(fresh, today, escala_tom=config.escala_tom)

    if config.owner_chat_id is None:
        log_event(log, "digest_no_owner_chat_id", level=30, count=len(fresh))
        return DigestResult(sent=False, count=len(fresh), tasks=fresh, text=text)

    try:
        channel.send(config.owner_chat_id, text)
    except Exception as exc:
        log_event(log, "digest_send_failed", level=40, error=str(exc), count=len(fresh))
        return DigestResult(sent=False, count=len(fresh), tasks=fresh, text=text)

    for t in fresh:
        state.mark_nudged(t.id, today)

    log_event(log, "digest_sent", count=len(fresh), task_ids=[t.id for t in fresh])
    return DigestResult(sent=True, count=len(fresh), tasks=fresh, text=text)
