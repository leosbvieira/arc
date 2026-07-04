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

from . import cadence
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
    return Task(
        id=t.id,
        name=t.name,
        area=t.area,
        status=t.status,
        due=due,
        last_done=t.last_done,
        assignee=t.assignee,
    )


def _open() -> list[_Task]:
    return [t for t in _MOCK if t.status == "open"]


def _grouped(tasks: list[_Task]) -> dict:
    areas = []
    for area in AREAS:
        items = [_display(t).model_dump() for t in tasks if t.area == area]
        if items:
            areas.append({"area": area, "tasks": items})
    return {"areas": areas}


async def list_by_area() -> dict:
    if settings.hermes_mock or not settings.hermes_api_key:
        return _grouped(_open())
    # TODO real: Hermes (profile Tarefas) via ClickUp MCP → parsear pra _Task[].
    raise NotImplementedError("modo real: Hermes/ClickUp MCP")


async def create(name: str, area: str) -> Task:
    global _next
    if settings.hermes_mock or not settings.hermes_api_key:
        t = _Task(f"t{_next}", name, area, due_offset=0)
        _next += 1
        _MOCK.append(t)
        return _display(t)
    raise NotImplementedError("modo real: Hermes/ClickUp MCP")


async def complete(task_id: str) -> bool:
    if settings.hermes_mock or not settings.hermes_api_key:
        for t in _MOCK:
            if t.id == task_id:
                t.status = "done"
                return True
        return False
    raise NotImplementedError("modo real: Hermes/ClickUp MCP")


async def run_digest() -> dict:
    """Calcula o digest de cobranças (dev/mock/fallback). Ver docstring do módulo."""
    if settings.hermes_mock or not settings.hermes_api_key:
        src = _open()
    else:
        raise NotImplementedError("modo real: Hermes/ClickUp MCP")

    selected = cadence.select(src)
    escala = cadence.DEFAULT_RULE.escala_tom
    return {
        "count": len(selected),
        "text": cadence.format_digest(selected, escala_tom=escala),
        "body": "\n".join(cadence.digest_lines(selected, escala_tom=escala)),
        "tasks": [_display(t).model_dump() for t in selected],
    }
