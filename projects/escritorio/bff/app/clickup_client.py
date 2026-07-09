"""Fonte real das tarefas: ClickUp REST v2. Uma list por área (space Personal).

Porta REST (não MCP): o BFF é um servidor comum, não uma IA. Autentica com token
pessoal (pk_...) no header Authorization. Ver development/LIGAR-DADOS-REAIS.md.
"""
from datetime import date, datetime

import httpx

from .config import settings

API = "https://api.clickup.com/api/v2"

# área -> list_id (workspace Personal 9007178855, descobertos 2026-07-05)
AREA_LISTS: dict[str, str] = {
    "Trabalho": "901327729093",
    "Finanças": "901327729095",
    "Saúde": "901327729097",
    "Pessoal": "901327729099",
}
LIST_AREA: dict[str, str] = {v: k for k, v in AREA_LISTS.items()}


def _headers() -> dict:
    # token pessoal do ClickUp vai cru no Authorization (sem "Bearer")
    return {"Authorization": settings.clickup_token, "Content-Type": "application/json"}


def _verify():
    """SSL: True normal; False ignora (rede com proxy MITM); ou caminho pro .pem da CA."""
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
    """Tarefas abertas das 4 áreas; cada dict ganha '_area'.

    ⚠ include_closed=false só corta status tipo 'closed'. As concluídas viram tipo
    'done' (ex.: status 'complete') e ainda vêm no GET — por isso filtramos aqui,
    senão a tarefa marcada como feita não some da lista.
    """
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=30, verify=_verify()) as client:
        for area, lid in AREA_LISTS.items():
            for t in await _list_tasks(client, lid):
                if ((t.get("status") or {}).get("type")) in ("done", "closed"):
                    continue
                t["_area"] = area
                out.append(t)
    return out


async def get_task(task_id: str) -> dict:
    """Tarefa completa (inclui description/text_content) — pro detalhe no app."""
    async with httpx.AsyncClient(timeout=30, verify=_verify()) as client:
        r = await client.get(f"{API}/task/{task_id}", headers=_headers())
        r.raise_for_status()
        return r.json()


async def create(name: str, area: str) -> dict:
    lid = AREA_LISTS[area]
    async with httpx.AsyncClient(timeout=30, verify=_verify()) as client:
        r = await client.post(f"{API}/list/{lid}/task", json={"name": name}, headers=_headers())
        r.raise_for_status()
        t = r.json()
        t["_area"] = area
        return t


async def complete(task_id: str) -> bool:
    # ⚠ confirmar no teste: o nome do status "concluído" varia por lista.
    # Se falhar, descubra com GET /list/{id} -> statuses[] e ajuste o valor abaixo.
    async with httpx.AsyncClient(timeout=30, verify=_verify()) as client:
        r = await client.put(
            f"{API}/task/{task_id}", json={"status": "complete"}, headers=_headers()
        )
        return r.status_code == 200
