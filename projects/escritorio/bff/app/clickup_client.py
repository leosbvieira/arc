"""Fonte real das tarefas: ClickUp REST v2. Uma list por área (space Personal).

Porta REST (não MCP): o BFF é um servidor comum, não uma IA. Autentica com token
pessoal (pk_...) no header Authorization. Ver development/LIGAR-DADOS-REAIS.md.
"""
import asyncio
from datetime import date, datetime

import httpx

from .config import settings

API = "https://api.clickup.com/api/v2"
# Só para trocar a home list de uma tarefa: a v2 não tem esse endpoint, e o caminho
# que tentava emular (adicionar no destino, remover da origem) é impossível — ver
# `move_task`. Todo o resto do arquivo continua na v2.
API_V3 = "https://api.clickup.com/api/v3"

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
    return await _fetch_list(
        list_id,
        params={
            "archived": "false",
            "subtasks": "false",
            "include_closed": "true" if include_closed else "false",
        },
        client=client,
    )


async def _fetch_list(
    list_id: str,
    params: dict | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """Busca tarefas com defaults explícitos, usando client compartilhado quando dado."""
    merged_params = {**_LIST_DEFAULT_PARAMS, **(params or {})}

    if client is not None:
        tasks: list[dict] = []
        page = int(merged_params.pop("page", 0))
        while True:
            r = await client.get(
                f"{API}/list/{list_id}/task",
                params={**merged_params, "page": page},
                headers=_headers(),
            )
            r.raise_for_status()
            payload = r.json()
            batch = payload.get("tasks", [])
            tasks.extend(batch)
            if payload.get("last_page") is True or len(batch) < 100:
                return tasks
            page += 1

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
    """Tarefas abertas das 10 áreas; cada dict ganha `_area`.

    Deduplica por id. A causa histórica era o `move_task` antigo, que deixava a
    tarefa NAS DUAS listas sempre que o DELETE da home list falhava — e ele falhava
    sempre. O dedupe continua: a tarefa pode legitimamente estar em mais de uma lista
    pelo ClickApp `Tasks in Multiple Lists`, e o resíduo das triagens antigas segue no
    ClickUp. Sem isso ela apareceria 2× na tela, 2× no digest e contaria 2× em
    "N abertas · N atrasadas".

    O desempate é pela ÁREA, não pela ordem de varredura (Staging é a 2ª de 10 em
    AREA_LISTS): Staging é o resíduo do move que falhou, a área de destino é a
    decisão do Leo. Mostrar o resíduo faria ele triar de novo o que já triou.

    As 10 listas são buscadas EM PARALELO. Sequencialmente eram 10 idas ao
    ClickUp uma depois da outra — medido em 09/ago: ~4,5s de piso em toda tela
    que depende de tarefa (Hoje, Tarefas, Mesa, Agenda, Shutdown, Revisão),
    contra 5-13ms das rotas que só leem o SQLite. O `gather` troca a soma das
    dez pela mais lenta delas.

    A ordem NÃO se perde: o gather preserva a ordem de AREA_LISTS, e a fusão
    continua acontecendo depois, no mesmo laço de antes. Fundir dentro das
    corrotinas tornaria o desempate dependente de quem responde primeiro."""
    out: list[dict] = []
    por_id: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        por_lista = await asyncio.gather(
            *(_fetch_list(list_id, client=client) for list_id in AREA_LISTS.values())
        )
        for area, tarefas in zip(AREA_LISTS, por_lista):
            for task in tarefas:
                if ((task.get("status") or {}).get("type")) in ("done", "closed"):
                    continue
                task["_area"] = area
                task_id = task.get("id")
                if task_id is None:
                    out.append(task)
                    continue
                anterior = por_id.get(task_id)
                if anterior is None:
                    por_id[task_id] = task
                    out.append(task)
                elif anterior["_area"] == STAGING and area != STAGING:
                    anterior.update(task)          # o destino vence o resíduo
    return out


async def count_open(list_id: str) -> int:
    """Quantidade retornada pelo ClickUp para uma lista aberta."""
    return len(await _fetch_list(list_id))


async def _contar_fechadas(params: dict) -> int:
    """Soma as tarefas com `date_done` nas 9 áreas (Staging fora), em paralelo.

    Mesma razão do `fetch_open`: eram 9 idas sequenciais ao ClickUp. Aqui a
    ordem é irrelevante — é uma soma —, então só o paralelismo importa.
    """
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        por_lista = await asyncio.gather(
            *(
                _fetch_list(list_id, params=params, client=client)
                for area, list_id in AREA_LISTS.items()
                if area != STAGING
            )
        )
    return sum(
        1 for tarefas in por_lista for task in tarefas if task.get("date_done")
    )


async def count_closed_since(ts_ms: int) -> int:
    """Tarefas fechadas desde ts_ms, excluindo a lista de triagem Staging."""
    return await _contar_fechadas({
        "include_closed": "true",
        "date_done_gt": str(ts_ms),
    })


async def count_closed_between(start_ms: int, end_ms: int) -> int:
    """Conta fechamentos na janela [start, end), excluindo o Staging."""
    return await _contar_fechadas({
        "include_closed": "true",
        "date_done_gt": str(start_ms),
        "date_done_lt": str(end_ms),
    })


async def get_task(task_id: str) -> dict:
    """Tarefa completa (inclui description/text_content) — pro detalhe no app."""
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        r = await client.get(f"{API}/task/{task_id}", headers=_headers())
        r.raise_for_status()
        return r.json()


async def move_task(task_id: str, to_list_id: str) -> bool:
    """Troca a HOME LIST da tarefa, que é o que a triagem quer dizer com "mover".

    O caminho anterior — adicionar no destino pelo ClickApp ``Tasks in Multiple
    Lists`` e remover da origem — não movia nada e nunca poderia: a origem é a home
    list da tarefa, e o ClickUp recusa removê-la com ``TASK_035 Task home list cannot
    be altered``. O add respondia 200 e o delete 400, então toda triagem deixava a
    tarefa NAS DUAS listas e reportava falha sem dizer por quê. Confirmado contra o
    ClickUp real em 2026-08-10 (é a origem do dedupe em `fetch_open`).

    A troca de home list só existe na v3, e o workspace sai do próprio GET — assim
    não entra configuração nova só para montar a URL.
    """
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        task_response = await client.get(
            f"{API}/task/{task_id}",
            headers=_headers(),
        )
        task_response.raise_for_status()
        task = task_response.json()
        workspace_id = task["team_id"]

        move_response = await client.put(
            f"{API_V3}/workspaces/{workspace_id}/tasks/{task_id}/home_list/{to_list_id}",
            headers=_headers(),
            json={},
        )
        move_response.raise_for_status()

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


async def set_due(task_id: str, due_ts: float, *, due_date_time: bool = False) -> bool:
    """Remarca o prazo. Mesma guarda do complete: só tasks das listas do Aeternum."""
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify()) as client:
        response = await client.get(f"{API}/task/{task_id}", headers=_headers())
        response.raise_for_status()
        list_id = str((response.json().get("list") or {}).get("id"))

        if list_id not in AREA_LISTS.values():
            return False

        response = await client.put(
            f"{API}/task/{task_id}",
            json={"due_date": int(due_ts * 1000), "due_date_time": due_date_time},
            headers=_headers(),
        )
        return response.status_code == 200


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
