"""Regras de cadência do digest — portadas do cutuca (cadence.py + nudge.py).

Puras/determinísticas: decidem 'cobrar ou não', o tom, e formatam. Sem I/O, sem LLM.
Fonte validada: ../../cutuca/src/cutuca/{cadence,nudge}.py (50 testes).
Operam por duck-typing sobre qualquer task com: status, days_overdue,
days_until_due, days_since_update, name, assignee.
"""

from dataclasses import dataclass

# Status que significam "não precisa mais cobrar" (case-insensitive).
CLOSED = frozenset(
    {
        "closed", "complete", "completed", "done", "resolved", "cancelled", "canceled",
        "concluído", "concluido", "concluída", "concluida", "cancelado", "cancelada",
        "finalizado", "finalizada", "arquivado",
    }
)

TONE_MARKERS = {"no_prazo": "🟡", "leve": "🟠", "firme": "🔴", "urgente": "🚨"}


@dataclass
class Rule:
    vence_em_dias: int | None = 0      # cobra se vence hoje..+N
    atrasada: bool = True              # cobra qualquer atrasada
    sem_update_dias: int | None = 3    # cobra se parada há >= N dias
    escala_tom: bool = True


DEFAULT_RULE = Rule()


def is_closed(status: str | None) -> bool:
    return bool(status) and status.strip().lower() in CLOSED


def tone(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "no_prazo"
    if days_overdue <= 2:
        return "leve"
    if days_overdue <= 6:
        return "firme"
    return "urgente"


def tone_name(days_overdue: int | None) -> str:
    """Nome da severidade a partir dos dias de atraso (positivo = atrasada).

    Deriva de `tone()` — única tabela de thresholds — e só acrescenta o caso 'sem
    due' (None -> no_prazo). É a fonte única que /tasks, /digest e /tasks/{id} usam.
    """
    return "no_prazo" if days_overdue is None else tone(days_overdue)


def needs_nudge(t, rule: Rule = DEFAULT_RULE) -> bool:
    """Cobra se QUALQUER ramo bater; nunca cobra tarefa fechada."""
    if is_closed(t.status):
        return False
    # atrasada
    if rule.atrasada and t.days_until_due is not None and t.days_overdue > 0:
        return True
    # vence em breve (hoje..+N, ainda não atrasada)
    if rule.vence_em_dias is not None and t.days_until_due is not None:
        if 0 <= t.days_until_due <= rule.vence_em_dias:
            return True
    # parada (sem update)
    if rule.sem_update_dias is not None and t.days_since_update is not None:
        if t.days_since_update >= rule.sem_update_dias:
            return True
    return False


def select(tasks, rule: Rule = DEFAULT_RULE) -> list:
    return [t for t in tasks if needs_nudge(t, rule)]


def _line(t, escala_tom: bool) -> str:
    overdue = t.days_overdue
    until = t.days_until_due
    assignee = t.assignee or "sem responsável"

    if overdue > 0:
        when = f"atrasada {overdue}d"
    elif until == 0:
        when = "vence hoje"
    elif until is not None and until > 0:
        when = f"vence em {until}d"
    else:
        since = t.days_since_update
        when = f"parada há {since}d" if since is not None else "sem update"

    marker = (TONE_MARKERS.get(tone(overdue), "") + " ") if escala_tom else ""
    return f"{marker}{t.name} — {assignee} · {when}"


def digest_lines(tasks, escala_tom: bool = True) -> list[str]:
    ordered = sorted(tasks, key=lambda t: t.days_overdue, reverse=True)
    return [_line(t, escala_tom) for t in ordered]


def format_digest(tasks, escala_tom: bool = True) -> str:
    header = f"🔔 Cobranças de hoje ({len(tasks)}):"
    return "\n".join([header, *digest_lines(tasks, escala_tom)])
