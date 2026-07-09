"""Fonte real das tarefas: ClickUp REST v2. Uma list por área (space Personal).

Porta REST (não MCP): o BFF é um servidor comum, não uma IA. Autentica com token
pessoal (pk_...) no header Authorization. Ver development/LIGAR-DADOS-REAIS.md.
"""
from datetime import date, datetime

import httpx

from .config import settings

API = "https://api.clickup.com/api/v2"

# área -> list_id (space Personal 90133461895). As 10 áreas normativas do Aeternum
# (Spec §8/D14): Trabalho mantida + 3 renomeadas (Finanças→Finance, Saúde→Corpo,
# Pessoal→Responsabilidade) + 6 criadas. Setup real em scripts/setup_clickup.py (2026-07-09).
AREA_LISTS: dict[str, str] = {
    "Trabalho": "901327729093",
    "Staging": "901327803429",
    "Corpo": "901327729097",
    "Saúde Mental": "901327803430",
    "Responsabilidade": "901327729099",
    "Finance": "901327729095",
    "Carreira": "901327803431",
    "Estudo": "901327803432",
    "Relacionamentos": "901327803433",
    "Lazer": "901327803434",
}
LIST_AREA: dict[str, str] = {v: k for k, v in AREA_LISTS.items()}

# list_id -> status de fechamento REAL da lista (GET /list/{id} statuses[] type done/closed).
# Literal por lista, NÃO comprehension: o nome do status "concluído" pode variar por lista;
# hoje as 10 fecham em "complete" (confirmado via API no setup 2026-07-09), mas o mapa mantém
# isso auditável e à prova de divergência futura. complete() resolve o status por aqui.
DONE_STATUS: dict[str, str] = {
    "901327729093": "complete",
    "901327803429": "complete",
    "901327729097": "complete",
    "901327803430": "complete",
    "901327729099": "complete",
    "901327729095": "complete",
    "901327803431": "complete",
    "901327803432": "complete",
    "901327803433": "complete",
    "901327803434": "complete",
}

# Lista de triagem: capturas caem aqui antes de virar tarefa de área. "Staging" já está em
# AREA_LISTS (Task 6), então _staging_metrics no digest opera com dados reais. A const dá o
# nome canônico p/ quem referencia a triagem sem hardcodar a string.
STAGING = "Staging"


def _headers() -> dict:
    # token pessoal do ClickUp vai cru no Authorization (sem "Bearer")
    return {"Authorization": settings.clickup_token, "Content-Type": "application/json"}


def ssl_verify():
    """SSL: True normal; False ignora (rede com proxy MITM); ou caminho pro .pem da CA.

    Público (sem `_`) porque scripts/setup_clickup.py importa este helper — o bloco SSL
    é a única forma correta de falar com o ClickUp atrás do proxy MITM corporativo.
    """
    v = (settings.clickup_verify_ssl or "true").lower()
    if v == "false":
        return False
    if v == "true":
        return True
    return settings.clickup_verify_ssl  # caminho do bundle .pem


def days_from_ms(ms) -> int | None:
    """Dias de calendário de hoje até a data do timestamp (ms). 0=hoje, <0 passado.

    ClickUp guarda due_date "só data" num horário fixo (aparece ~04:00). Por isso
    comparamos por DATA de calendário (local), não por delta bruto — senão "vence
    hoje de manhã" viraria "atrasada 1d".
    """
    if ms in (None, "", 0, "0"):
        return None
    due = datetime.fromtimestamp(int(ms) / 1000).date()
    return (due - date.today()).days


async def _list_tasks(client: httpx.AsyncClient, list_id: str) -> list[dict]:
    r = await client.get(
        f"{API}/list/{list_id}/task",
        params={"archived": "false", "subtasks": "false", "include_closed": "false"},
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json().get("tasks", [])


async def fetch_open() -> list[dict]:
    """Tarefas abertas das 10 áreas; cada dict ganha '_area'.

    ⚠ include_closed=false só corta status tipo 'closed'. As concluídas viram tipo
    'done' (ex.: status 'complete') e ainda vêm no GET — por isso filtramos aqui,
    senão a tarefa marcada como feita não some da lista.
    """
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        for area, lid in AREA_LISTS.items():
            for t in await _list_tasks(client, lid):
                if ((t.get("status") or {}).get("type")) in ("done", "closed"):
                    continue
                t["_area"] = area
                out.append(t)
    return out


async def get_task(task_id: str) -> dict:
    """Tarefa completa (inclui description/text_content) — pro detalhe no app."""
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        r = await client.get(f"{API}/task/{task_id}", headers=_headers())
        r.raise_for_status()
        return r.json()


async def create(name: str, area: str, tags: list[str] | None = None,
                 due_ts: float | None = None, description: str | None = None) -> dict:
    """Cria uma task na list da área. `due_ts` (epoch em SEGUNDOS) vira `due_date` em ms
    com `due_date_time` (hora marcada, não só o dia); `description` guarda o link do Raw e
    o marker de idempotência da captura (Task 9). `tags`/`due_ts`/`description` são opcionais
    pra não quebrar quem chama posicional (tasks.create)."""
    lid = AREA_LISTS[area]
    body: dict = {"name": name}
    if tags:
        body["tags"] = tags   # ClickUp cria a tag na hora se não existir (ex.: "aguardando")
    if due_ts is not None:
        body["due_date"] = int(due_ts * 1000)   # ClickUp espera epoch-ms
        body["due_date_time"] = True
    if description is not None:
        body["description"] = description
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        r = await client.post(f"{API}/list/{lid}/task", json=body, headers=_headers())
        r.raise_for_status()
        t = r.json()
        t["_area"] = area
        return t


async def complete(task_id: str) -> bool:
    """Fecha a task no status de conclusão REAL da lista dela (DONE_STATUS), não num literal
    fixo — o nome do status 'done' varia por lista. Descobre a lista pelo próprio GET da task
    (`list.id`) e cai em 'complete' (done default do ClickUp) se a lista não estiver mapeada."""
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        g = await client.get(f"{API}/task/{task_id}", headers=_headers())
        g.raise_for_status()
        list_id = str((g.json().get("list") or {}).get("id"))
        r = await client.put(
            f"{API}/task/{task_id}",
            json={"status": DONE_STATUS.get(list_id, "complete")},
            headers=_headers(),
        )
        return r.status_code == 200
