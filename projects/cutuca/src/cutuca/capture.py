"""Flow A orchestration: message -> parse -> create -> confirm, with ask-back on
ambiguity (SPEC FR-1/FR-2). No network of its own — it composes the parser and the
ClickUp client, both injectable, so it is unit-tested end to end without a network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional

from .config import Config
from .logging_setup import get_logger, log_event
from .parser import ParseError, missing_fields, parse_task
from .timeutil import get_tz, iso_to_ms, today_in

log = get_logger("cutuca.capture")

_ASKBACK_LABELS = {
    "assignee": "pra quem?",
    "prazo_iso": "qual o prazo?",
}


@dataclass
class Reply:
    kind: str          # "created" | "askback" | "error"
    text: str
    task: Any = None


def _askback_text(missing: list[str]) -> str:
    if set(missing) >= {"assignee", "prazo_iso"}:
        return "Entendi a tarefa, mas faltou: pra quem e qual o prazo?"
    asks = " e ".join(_ASKBACK_LABELS[m] for m in missing if m in _ASKBACK_LABELS)
    return f"Faltou {asks}"


def _format_prazo(prazo_iso: Optional[str]) -> str:
    if not prazo_iso:
        return "sem prazo"
    try:
        d = date.fromisoformat(prazo_iso)
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return prazo_iso


def handle_message(
    text: str,
    *,
    clickup,
    config: Config,
    parse: Callable = parse_task,
    now: Optional[date] = None,
) -> Reply:
    tz = get_tz(config.timezone)
    today = now or today_in(tz)

    try:
        parsed = parse(
            text,
            model=config.llm.model,
            max_tokens=config.llm.max_tokens,
            today=today,
            timeout=config.llm.timeout_seconds,
        )
    except ParseError as exc:
        log_event(log, "parse_failed", level=40, error=str(exc))
        return Reply("error", "Tive um problema pra ler isso agora. Me manda de novo em instantes?")

    if parsed is None:
        log_event(log, "parse_unrecognized", text=text[:200])
        return Reply("askback", "Não peguei a tarefa. Me manda: o que fazer, pra quem e o prazo.")

    missing = missing_fields(parsed)
    if missing:
        log_event(log, "parse_incomplete", missing=missing, titulo=parsed.get("titulo"))
        return Reply("askback", _askback_text(missing))

    # complete → create in ClickUp
    try:
        assignee_ids = clickup.resolve_assignees(
            [parsed["assignee"]], config.clickup.list_id, config.clickup.assignee_overrides
        )
        due_ms = iso_to_ms(parsed["prazo_iso"], tz)
        task = clickup.create_task(
            config.clickup.list_id,
            parsed["titulo"],
            assignee_ids=assignee_ids,
            due_date_ms=due_ms,
        )
    except Exception as exc:  # ClickUpError, network, etc.
        log_event(log, "clickup_create_failed", level=40, error=str(exc), titulo=parsed.get("titulo"))
        return Reply("error", "Consegui ler, mas falhei ao criar no ClickUp. Tenta de novo?")

    if not assignee_ids:
        log_event(log, "assignee_unresolved", assignee=parsed["assignee"], task_id=getattr(task, "id", None))

    log_event(
        log, "task_created",
        task_id=getattr(task, "id", None), assignee=parsed["assignee"],
        prazo=parsed["prazo_iso"], titulo=parsed["titulo"],
    )
    confirm = f"✅ criei: {parsed['titulo']} · {parsed['assignee']} · vence {_format_prazo(parsed['prazo_iso'])}"
    return Reply("created", confirm, task=task)
