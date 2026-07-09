"""Tarefas por área + recência, e o digest (cobranças) portado do cutuca.

MOCK (default): lista canned em memória — reseta ao reiniciar. De propósito:
as tarefas REAIS moram no ClickUp (via Hermes), não aqui (glass-not-store, D-1).
REAL (HERMES_MOCK=false): pedir ao Hermes (profile Tarefas) via ClickUp MCP.

O digest (`run_digest`) aqui é o caminho DEV/MOCK e o fallback: o BFF calcula com as
regras do cutuca (cadence.py). Em produção com o Hermes, o cron calcula o digest e usa
POST /internal/notify (D-14). As regras de cadência são as mesmas nos dois casos.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from . import cadence, clickup_client
from .config import settings

AREAS = ["Trabalho", "Finanças", "Saúde", "Pessoal"]


class Task(BaseModel):
    """Shape da API (o que o app recebe)."""

    id: str
    name: str
    area: str
    status: str = "open"
    due: str | None = None
    last_done: str | None = None
    assignee: str | None = None
    days_overdue: int | None = None   # positivo = atrasada; None = sem due
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


_MOCK: list[_Task] = [
    _Task("t1", "Relatório mensal", "Trabalho", due_offset=0, assignee="Ana"),
    _Task("t2", "Pagar fatura do cartão", "Finanças", due_offset=-2),
    _Task("t3", "Dentista", "Saúde", last_done="há 7 meses"),
    _Task("t4", "Treino", "Saúde", due_offset=0),
    _Task("t5", "Ligar pro contador", "Pessoal", update_offset=5),
    _Task("t6", "Renovar seguro do carro", "Finanças", due_offset=-8),
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
    status = (t.get("status") or {}).get("status")  # ClickUp: status é objeto {status: "..."}
    assignees = t.get("assignees") or []
    return _Task(
        id=str(t["id"]),
        name=t.get("name", ""),
        area=t.get("_area", "Pessoal"),
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
    return _grouped(_open())  # mock


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
        return await clickup_client.complete(task_id)
    for t in _MOCK:
        if t.id == task_id:
            t.status = "done"
            return True
    return False


async def run_digest() -> dict:
    """Calcula o digest de cobranças (regras do cutuca em cadence.py)."""
    if _use_clickup():
        src = [_from_clickup(t) for t in await clickup_client.fetch_open()]
    else:
        src = _open()

    selected = cadence.select(src)
    escala = cadence.DEFAULT_RULE.escala_tom
    return {
        "count": len(selected),
        "text": cadence.format_digest(selected, escala_tom=escala),
        "body": "\n".join(cadence.digest_lines(selected, escala_tom=escala)),
        "tasks": [_display(t).model_dump() for t in selected],
    }


async def get_detail(task_id: str) -> dict | None:
    """Detalhe de 1 tarefa (com descrição) pro app abrir ao tocar. None se não achar."""
    if _use_clickup():
        t = await clickup_client.get_task(task_id)
        lst = t.get("list") or {}
        t["_area"] = clickup_client.LIST_AREA.get(str(lst.get("id")), lst.get("name") or "Pessoal")
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
