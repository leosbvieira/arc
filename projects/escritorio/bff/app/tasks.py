"""Tarefas por área + recência, e o digest (cobranças) portado do cutuca.

MOCK (default): lista canned em memória — reseta ao reiniciar. De propósito:
as tarefas REAIS moram no ClickUp (via Hermes), não aqui (glass-not-store, D-1).
REAL (HERMES_MOCK=false): pedir ao Hermes (profile Tarefas) via ClickUp MCP.

O digest (`run_digest`) aqui é o caminho DEV/MOCK e o fallback: o BFF calcula com as
regras do cutuca (cadence.py). Em produção com o Hermes, o cron calcula o digest e usa
POST /internal/notify (D-14). As regras de cadência são as mesmas nos dois casos.
"""

import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel

from . import cadence, clickup_client, store
from .config import settings

AREAS = ["Trabalho", "Staging", "Corpo", "Saúde Mental", "Responsabilidade",
         "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer"]


class Task(BaseModel):
    """Shape da API (o que o app recebe)."""

    id: str
    name: str
    area: str
    status: str = "open"
    due: str | None = None
    last_done: str | None = None
    assignee: str | None = None
    days_overdue: int | None = None   # positivo = atrasada; negativo = dias restantes (futura); None = sem due
    severity: str = "no_prazo"        # fonte única no back (cadence.tone_name)


@dataclass
class _Task:
    """Task interna com offsets relativos a hoje (cadência determinística)."""

    id: str
    name: str
    area: str
    status: str = "open"
    due_offset: int | None = None      # dias até vencer: 0=hoje, <0 atrasada, >0 futuro
    update_offset: int | None = None   # dias desde o último update (staleness)
    last_done: str | None = None       # rótulo de recência (hábitos), só exibição
    assignee: str | None = None

    # interface que cadence.py espera (mesma semântica do Task do cutuca)
    @property
    def days_overdue(self) -> int:
        return -self.due_offset if self.due_offset is not None else 0

    @property
    def days_until_due(self) -> int | None:
        return self.due_offset

    @property
    def days_since_update(self) -> int | None:
        return self.update_offset

    def due_label(self) -> str | None:
        if self.due_offset is None:
            return None
        if self.due_offset < 0:
            return f"atrasada {-self.due_offset}d"
        if self.due_offset == 0:
            return "vence hoje"
        return f"vence em {self.due_offset}d"


# seed do modo mock: áreas no vocabulário normativo das 10 listas (Task 6); senão
# `_grouped` (que itera AREAS) não acha essas tarefas e o modo dev mostra só "Trabalho".
_MOCK: list[_Task] = [
    _Task("t1", "Relatório mensal", "Trabalho", due_offset=0, assignee="Ana"),
    _Task("t2", "Pagar fatura do cartão", "Finance", due_offset=-2),
    _Task("t3", "Dentista", "Corpo", last_done="há 7 meses"),
    _Task("t4", "Treino", "Corpo", due_offset=0),
    _Task("t5", "Ligar pro contador", "Responsabilidade", update_offset=5),
    _Task("t6", "Renovar seguro do carro", "Finance", due_offset=-8),
]
_next = 7


def _display(t: _Task) -> Task:
    due = t.due_label()
    if due is None and t.update_offset is not None and t.update_offset >= 1:
        due = f"parada há {t.update_offset}d"
    # due_offset é dias até vencer (negativo = atrasada); days_overdue inverte o sinal
    # (positivo = atrasada), None quando não há due. Ponto único: todas as rotas e
    # ambas as fontes (mock/ClickUp) passam por aqui, então a severidade nasce uma vez.
    days_overdue = -t.due_offset if t.due_offset is not None else None
    return Task(
        id=t.id,
        name=t.name,
        area=t.area,
        status=t.status,
        due=due,
        last_done=t.last_done,
        assignee=t.assignee,
        days_overdue=days_overdue,
        severity=cadence.tone_name(days_overdue),
    )


def _open() -> list[_Task]:
    return [t for t in _MOCK if t.status == "open"]


def _use_clickup() -> bool:
    return settings.tasks_source == "clickup" and bool(settings.clickup_token)


def _from_clickup(t: dict) -> _Task:
    """ClickUp task JSON -> _Task interno.

    update_offset fica None nesta 1ª versão: só cobramos por vencimento (due). O nudge
    por 'parada há Xd' (staleness) a gente liga depois de ver os dados reais, senão
    inunda a Revisão com tudo que não foi tocado em 3 dias.
    """
    status = (t.get("status") or {}).get("status")
    assignees = t.get("assignees") or []
    return _Task(
        id=str(t["id"]),
        name=t.get("name", ""),
        area=t.get("_area", "Staging"),
        status=status or "open",
        due_offset=clickup_client.days_from_ms(t.get("due_date")),
        update_offset=None,
        assignee=(assignees[0].get("username") if assignees else None),
    )


def _grouped(tasks: list[_Task]) -> dict:
    areas = []
    for area in AREAS:
        items = [_display(t).model_dump() for t in tasks if t.area == area]
        if items:
            areas.append({"area": area, "tasks": items})
    return {"areas": areas}


async def list_by_area() -> dict:
    if _use_clickup():
        return _grouped([_from_clickup(t) for t in await clickup_client.fetch_open()])
    return _grouped(_open())


async def create(name: str, area: str) -> Task:
    if _use_clickup():
        return _display(_from_clickup(await clickup_client.create(name, area)))
    global _next
    t = _Task(f"t{_next}", name, area, due_offset=0)
    _next += 1
    _MOCK.append(t)
    return _display(t)


async def complete(task_id: str) -> bool:
    if _use_clickup():
        ok = await clickup_client.complete(task_id)
        if ok:
            store.log_event("task_completed", ref=task_id)
        return ok
    for t in _MOCK:
        if t.id == task_id:
            t.status = "done"
            store.log_event("task_completed", ref=task_id)
            return True
    return False


def weekly_review_pack(today: str | None = None) -> dict:
    """Números da semana ISO corrente, com fronteira local em America/Sao_Paulo."""
    from datetime import date, datetime, time, timedelta
    from zoneinfo import ZoneInfo

    local_tz = ZoneInfo("America/Sao_Paulo")
    ref = date.fromisoformat(today) if today else datetime.now(local_tz).date()
    monday = ref - timedelta(days=ref.weekday())
    since_iso = monday.isoformat()
    since_ts = datetime.combine(monday, time.min, tzinfo=local_tz).timestamp()

    por_rotina: dict[str, dict] = {}
    for row in store.get_checks_since(since_iso):
        item = por_rotina.setdefault(
            row["rotina"],
            {"feitos": 0, "dias": 0},
        )
        item["dias"] += 1
        item["feitos"] += 1 if row["feito"] else 0

    pct = (
        round(
            100
            * sum(item["feitos"] / item["dias"] for item in por_rotina.values())
            / len(por_rotina)
        )
        if por_rotina
        else 0
    )
    sessoes = [
        session
        for session in store.list_sessions_since(since_ts)
        if session["tipo"] == "leitura"
    ]
    iso_week = ref.isocalendar()

    return {
        "week": f"{iso_week.year}-W{iso_week.week:02d}",
        "desde": since_iso,
        "scorecard": {"pct": pct, "por_rotina": por_rotina},
        "dailies": store.count_events_since("closing_approved", since_ts),
        "capturas": store.count_events_since("capture_done", since_ts),
        "sessoes_leitura": {
            "n": len(sessoes),
            "min_total": sum(session["duracao_s"] for session in sessoes) // 60,
        },
        "tarefas_concluidas": None,
        "staging_pendentes": None,
    }


def weekly_review_text(today: str | None = None) -> str:
    """Texto compacto do nudge semanal; métricas ClickUp ficam no endpoint."""
    pack = weekly_review_pack(today)
    rotinas = " · ".join(
        f"{rotina} {dados['feitos']}/{dados['dias']}"
        for rotina, dados in sorted(
            pack["scorecard"]["por_rotina"].items(),
        )
    )
    return (
        f"semana {pack['week']} — scorecard {pack['scorecard']['pct']}%\n"
        f"{rotinas or 'sem checks registrados'}\n"
        f"dailies {pack['dailies']}/7 · capturas {pack['capturas']} · "
        f"leitura {pack['sessoes_leitura']['n']} sessões "
        f"({pack['sessoes_leitura']['min_total']} min)"
    )


# --- digest v2 (C10/C11 + lei 7) --------------------------------------------
# O texto INTEIRO da mensagem do Telegram aparece no lockscreen, então linhas de áreas
# sensíveis saem neutralizadas nesse canal; o app (atrás do login) mostra tudo. O digest
# envia se houver QUALQUER linha acionável (tarefa, staging, rotina ou captura travada).

MARKER = {"no_prazo": "🟡", "leve": "🟠", "firme": "🔴", "urgente": "🚨"}


def _norm(s: str) -> str:
    """Fold p/ comparação robusta de área (lei 7 FAIL-CLOSED): drift de caixa/acento/espaço
    entre o nome da lista no ClickUp e o CSV de config não pode vazar conteúdo no lockscreen.
    NFKD → remove marcas de acento → casefold → strip."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().strip()


def _sensitive_areas() -> set[str]:
    return {_norm(a) for a in settings.sensitive_areas.split(",") if a.strip()}


def render_digest_lines(tasks: list[Task], for_channel: str) -> list[str]:
    """for_channel: 'telegram' neutraliza áreas sensíveis (lei 7); 'app' mostra tudo."""
    lines = []
    for t in sorted(tasks, key=lambda x: -(x.days_overdue or 0)):
        m = MARKER.get(t.severity, "🟡")
        atraso = f"{t.days_overdue}d de atraso" if (t.days_overdue or 0) > 0 else "no prazo"
        if for_channel == "telegram" and _norm(t.area or "") in _sensitive_areas():
            lines.append(f"{m} 1 pendência de saúde ({atraso}) — abre o app")
        else:
            safe_name = t.name.replace(chr(10), " ")
            lines.append(f"{m} {safe_name} · {t.area} ({atraso})")
    return lines


def staging_line(count: int, oldest_days: int | None) -> str | None:
    if count and oldest_days is not None and oldest_days >= settings.staging_age_days:
        return f"📥 staging: {count} itens, mais velho {oldest_days}d — triar no ClickUp"
    return None


def routine_lines(today: str | None = None) -> list[str]:
    """Furo = dia COM fechamento e check false; >=N/7d vira padrão. Linguagem factual (lei 4)."""
    from datetime import date, timedelta
    ref = date.fromisoformat(today) if today else date.today()
    since = (ref - timedelta(days=7)).isoformat()
    misses: dict[str, int] = {}
    for row in store.get_checks_since(since):
        if not row["feito"]:
            misses[row["rotina"]] = misses.get(row["rotina"], 0) + 1
    return [f"🔁 {r}: {n} furos nos últimos 7 dias"
            for r, n in sorted(misses.items()) if n >= settings.routine_miss_threshold]


def _age_days(ms) -> int | None:
    """Idade em dias desde a criação. ClickUp date_created é epoch-ms UTC — comparamos os
    DOIS lados em UTC (não `date.today()` local) pra não ter skew de fronteira de dia, e o
    parse fica independente da tz da máquina. Valor ausente/não-numérico → None."""
    from datetime import datetime, timezone
    if ms in (None, "", 0, "0"):
        return None
    try:
        created = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    return (datetime.now(timezone.utc).date() - created).days


def _staging_metrics(raw: list[dict], area: str) -> tuple[int, int | None]:
    """(qtd, idade-do-mais-velho-em-dias) da lista Staging. Degrada p/ (0, None) enquanto
    a lista não existir no ClickUp (Task 6): `area` não está em AREA_LISTS, logo fetch_open
    nem a traz. Idade por `date_created`."""
    if area not in clickup_client.AREA_LISTS:
        return 0, None
    items = [t for t in raw if t.get("_area") == area]
    ages = [a for a in (_age_days(t.get("date_created")) for t in items) if a is not None]
    return len(items), (max(ages) if ages else None)


async def run_digest() -> dict:
    """Digest v2: cobranças por área (staging excluído) + staging envelhecendo + rotina-
    padrão + capturas travadas. Dois corpos — `body_telegram` neutraliza áreas sensíveis
    (lei 7), `body_app` mostra tudo — mais a lista `tasks` (fresca p/ a Home)."""
    staging = clickup_client.STAGING
    staging_count, staging_oldest = 0, None
    if _use_clickup():
        raw = await clickup_client.fetch_open()
        src = [_from_clickup(t) for t in raw]
        staging_count, staging_oldest = _staging_metrics(raw, staging)
    else:
        src = _open()

    selected = [t for t in cadence.select(src) if t.area != staging]
    tasks = [_display(t) for t in selected]

    extra: list[str] = []
    sl = staging_line(staging_count, staging_oldest)
    if sl:
        extra.append(sl)
    extra.extend(routine_lines())
    n_failed = len(store.failed_captures())
    if n_failed:
        extra.append(f"⚠ {n_failed} capturas não processadas — abrir o app")

    body_telegram = "\n".join([*render_digest_lines(tasks, "telegram"), *extra])
    body_app = "\n".join([*render_digest_lines(tasks, "app"), *extra])
    return {"tasks": tasks, "body_telegram": body_telegram,
            "body_app": body_app, "lines_extra": extra}


async def get_detail(task_id: str) -> dict | None:
    """Detalhe de 1 tarefa (com descrição) pro app abrir ao tocar.

    Fail-closed: uma tarefa fora das listas próprias não é exposta pelo BFF.
    """
    if _use_clickup():
        t = await clickup_client.get_task(task_id)
        lst = t.get("list") or {}
        list_id = str(lst.get("id"))
        if list_id not in clickup_client.AREA_LISTS.values():
            return None
        t["_area"] = clickup_client.LIST_AREA[list_id]
        base = _display(_from_clickup(t)).model_dump()
        base["priority"] = (t.get("priority") or {}).get("priority") if t.get("priority") else None
        base["description"] = (t.get("text_content") or t.get("description") or "").strip()
        base["url"] = t.get("url")
        return base
    for t in _MOCK:
        if t.id == task_id:
            base = _display(t).model_dump()
            base.update(priority=None, description="", url=None)
            return base
    return None
