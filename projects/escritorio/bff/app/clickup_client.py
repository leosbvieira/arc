"""Fonte real das tarefas: ClickUp REST v2. Uma list por área (space Personal).

Porta REST (não MCP): o BFF é um servidor comum, não uma IA. Autentica com token
pessoal (pk_...) no header Authorization. Ver development/LIGAR-DADOS-REAIS.md.
"""
from datetime import date, datetime

import httpx

from .config import settings

API = "https://api.clickup.com/api/v2"

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

STAGING = "Staging"

_LIST_DEFAULT_PARAMS = {
    "archived": "false",
    "subtasks": "false",
    "include_closed": "false",
}


def _headers() -> dict:
    return {
        "Authorization": settings.clickup_token,
        "Content-Type": "application/json",
    }


def ssl_verify():
    """SSL: True normal; False ignora; ou caminho pro .pem da CA."""
    v = (settings.clickup_verify_ssl or "true").lower()
    if v == "false":
        return False
    if v == "true":
        return True
    return settings.clickup_verify_ssl


def days_from_ms(ms) -> int | None:
    """Dias de calendário de hoje até a data do timestamp (ms)."""
    if ms in (None, "", 0, "0"):
        return None
    due = datetime.fromtimestamp(int(ms) / 1000).date()
    return (due - date.today()).days


async def _list_tasks(
    client: httpx.AsyncClient,
    list_id: str,
    *,
    include_closed: bool = False,
) -> list[dict]:
    r = await client.get(
        f"{API}/list/{list_id}/task",
        params={
            "archived": "false",
            "subtasks": "false",
            "include_closed": "true" if include_closed else "false",
        },
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json().get("tasks", [])


async def _fetch_list(
    list_id: str,
    params: dict | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Busca tarefas com defaults explícitos, usando client compartilhado quando dado."""
    merged_params = {**_LIST_DEFAULT_PARAMS, **(params or {})}

    if client is not None:
        r = await client.get(
            f"{API}/list/{list_id}/task",
            params=merged_params,
            headers=_headers(),
        )
        r.raise_for_status()
        return r.json().get("tasks", [])

    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as owned_client:
        return await _fetch_list(
            list_id,
            params=merged_params,
            client=owned_client,
        )


async def find_task_by_marker(list_id: str, marker: str) -> str | None:
    """Procura inclusive tarefas fechadas cujo conteúdo contenha o marker da captura."""
    if not marker:
        return None
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        tasks = await _list_tasks(client, list_id, include_closed=True)
    for task in tasks:
        for field in ("description", "text_content"):
            content = task.get(field)
            if isinstance(content, str) and marker in content:
                task_id = task.get("id")
                return str(task_id) if task_id is not None else None
    return None


async def fetch_open() -> list[dict]:
    """Tarefas abertas das 10 áreas; cada dict ganha `_area`."""
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        for area, list_id in AREA_LISTS.items():
            for task in await _fetch_list(list_id, client=client):
                if ((task.get("status") or {}).get("type")) in ("done", "closed"):
                    continue
                task["_area"] = area
                out.append(task)
    return out


async def count_open(list_id: str) -> int:
    """Quantidade retornada pelo ClickUp para uma lista aberta."""
    return len(await _fetch_list(list_id))


async def count_closed_since(ts_ms: int) -> int:
    """Tarefas fechadas desde ts_ms, excluindo a lista de triagem Staging."""
    total = 0
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        for area, list_id in AREA_LISTS.items():
            if area == STAGING:
                continue
            listed = await _fetch_list(
                list_id,
                params={
                    "include_closed": "true",
                    "date_done_gt": str(ts_ms),
                },
                client=client,
            )
            total += sum(1 for task in listed if task.get("date_done"))
    return total


async def get_task(task_id: str) -> dict:
    """Tarefa completa (inclui description/text_content) — pro detalhe no app."""
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        r = await client.get(f"{API}/task/{task_id}", headers=_headers())
        r.raise_for_status()
        return r.json()


async def move_task(task_id: str, to_list_id: str) -> bool:
    """Move uma tarefa usando o ClickApp ``Tasks in Multiple Lists``.

    A lista de origem vem do GET para que a remoção não dependa de estado local.
    O chamador trata individualmente falhas como o ClickApp desabilitado.
    """
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        task_response = await client.get(
            f"{API}/task/{task_id}",
            headers=_headers(),
        )
        task_response.raise_for_status()
        task = task_response.json()
        from_list_id = task["list"]["id"]

        add_response = await client.post(
            f"{API}/list/{to_list_id}/task/{task_id}",
            headers=_headers(),
        )
        add_response.raise_for_status()

        remove_response = await client.delete(
            f"{API}/list/{from_list_id}/task/{task_id}",
            headers=_headers(),
        )
        remove_response.raise_for_status()

    return True


async def create(
    name: str,
    area: str,
    tags: list[str] | None = None,
    due_ts: float | None = None,
    description: str | None = None,
    due_date_time: bool = True,
) -> dict:
    """Cria uma task na list da área."""
    lid = AREA_LISTS[area]
    body: dict = {"name": name}
    if tags:
        body["tags"] = tags
    if due_ts is not None:
        body["due_date"] = int(due_ts * 1000)
        body["due_date_time"] = due_date_time
    if description is not None:
        body["description"] = description
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        r = await client.post(
            f"{API}/list/{lid}/task",
            json=body,
            headers=_headers(),
        )
        r.raise_for_status()
        task = r.json()
        task["_area"] = area
        return task


async def complete(task_id: str) -> bool:
    """Fecha somente tasks pertencentes às listas próprias do Aeternum."""
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        response = await client.get(
            f"{API}/task/{task_id}",
            headers=_headers(),
        )
        response.raise_for_status()
        list_id = str((response.json().get("list") or {}).get("id"))

        if list_id not in AREA_LISTS.values():
            return False

        response = await client.put(
            f"{API}/task/{task_id}",
            json={"status": DONE_STATUS.get(list_id, "complete")},
            headers=_headers(),
        )
        return response.status_code == 200
