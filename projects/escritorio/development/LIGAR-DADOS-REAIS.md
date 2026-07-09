# Ligar dados reais (Tarefas + Revisão) — passo-a-passo

> **Objetivo:** trocar o mock do BFF por dados reais do ClickUp nas telas **Tarefas** e
> **Revisão**. Fazer com o PC ligado e testando cada passo. O app v2 já lida bem com o BFF
> fora do ar (skeleton + card "sem servidor"), então dá pra ir com calma.
>
> Status (2026-07-05): **LIGADO E VALIDADO** contra o ClickUp real. O rascunho de código
> abaixo virou o real em `bff/app/clickup_client.py` + `bff/app/tasks.py`. Confirmado:
> - **Decisão:** fonte = as **4 listas de área** (escritório = camada pessoal nova). Estão
>   vazias hoje; as tarefas de trabalho ficam fora (no 2.Daily etc.), de propósito.
> - **due_date "só data"** (aparece ~04:00) → comparado por **DATA de calendário** local,
>   senão "vence hoje de manhã" vira "atrasada 1d". (`days_from_ms`)
> - **status "concluído" = `complete`** (existe nas 4 listas) → completar pelo app funciona.
> - **SSL:** rede com proxy MITM → `CLICKUP_VERIFY_SSL=false` (mesmo motivo do `--trusted-host`).
> - `update_offset` fica None por ora (só cobra por vencimento; staleness a ligar depois).

---

## Decisão de arquitetura

**Tarefas/Revisão puxam do ClickUp via API REST direto no BFF** — não via Hermes.

Por quê: o Hermes só expõe *chat* (`/v1/chat/completions`). Pedir uma lista estruturada de
tarefas a um LLM é frágil e caro. A API REST do ClickUp é determinística e rápida. O Hermes
continua sendo o cérebro do **Chat** e da **Captura** (texto → tarefa/nota); o ClickUp é a
**fonte de verdade** das tarefas (glass-not-store, D-1 — o app não guarda nada).

```
App ──/tasks,/digest──> BFF ──REST──> ClickUp        (tarefas: determinístico)
App ──/capture───────> BFF ──chat──> Hermes ──MCP──> ClickUp/vault   (linguagem natural)
```

---

## IDs reais (workspace Personal, descobertos 2026-07-05)

- **Workspace (team) id:** `9007178855`
- **Space:** `Personal` (`90133461895`)
- **Área → list id:**

  | Área | List ID |
  |---|---|
  | Trabalho | `901327729093` |
  | Finanças | `901327729095` |
  | Saúde | `901327729097` |
  | Pessoal | `901327729099` |

> Obs.: existe uma lista **Finanças** antiga (`901310689433`) dentro da pasta `01.Planning`.
> **Não** use essa — as quatro acima são as do escritório (criadas juntas, IDs sequenciais).
>
> Para a Captura de leitura, depois: pasta **Livro** → lista `901310691642`; inbox de
> captura: **1. Captura** `901309163874` (no space Management).

---

## Passo 0 — Gerar o token do ClickUp

1. ClickUp → foto do perfil (canto inf. esq.) → **Settings** → **Apps**.
2. Em **API Token**, clique **Generate** (ou **Regenerate**). Copie o token (começa com `pk_...`).
3. Guarde — vai no `.env` do BFF (nunca no código, nunca no git).

---

## Passo 1 — Subir o BFF em mock e confirmar que o app conecta

Antes de tocar em ClickUp, valide o encanamento com o mock (garante que o app acha o BFF).

```powershell
cd C:\Users\Leonardo\GitHub\Arc\projects\escritorio\bff
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# instale com o python DO venv (à prova de PATH) e confiando nos hosts do PyPI
# (a rede tem SSL interceptado — cert self-signed na cadeia; sem --trusted-host o pip recusa):
.\.venv\Scripts\python.exe -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org -r requirements.txt
Copy-Item .env.example .env    # se ainda não existe
```

Edite o `.env` e troque no mínimo:
```
APP_PASSWORD=<a senha que você digita no app>
JWT_SECRET=<uma string longa aleatória>
```

Suba com `python -m uvicorn` (o `uvicorn` pelado pega o Python global; `-m` usa o do venv).
Host 0.0.0.0 pra o celular alcançar pela Wi-Fi:
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Confira:
- No PC: abrir `http://localhost:8000/health` → `{"ok":true,"mock":true}`.
- **IP:** o app aponta pra `http://192.168.80.109:8000` (em `app/src/api.ts`, `BFF_URL`).
  Rode `ipconfig` e confirme que o IPv4 da Wi-Fi ainda é esse. Se mudou, atualize `BFF_URL`.
- No celular (Expo Go, mesma Wi-Fi): logar com a `APP_PASSWORD`. Tarefas/Revisão devem
  mostrar o mock. Se aparecer o card **"sem servidor"** → firewall/IP/porta; ajuste e toque
  em *tentar de novo*.

> Firewall do Windows: na 1ª vez o uvicorn pode pedir permissão de rede — **permita** (rede
> privada). Se o celular não conectar, libere a porta 8000 no Firewall pra rede privada.

---

## Passo 2 — Configuração do ClickUp no BFF

**`bff/app/config.py`** — adicione ao `Settings`:
```python
    # ClickUp (fonte real das tarefas)
    tasks_source: str = "mock"          # "mock" | "clickup"
    clickup_token: str = ""             # pk_...
    clickup_verify_ssl: str = "true"    # "true" | "false" | caminho do .pem da CA corporativa
```

**`bff/.env`** — adicione:
```
TASKS_SOURCE=mock          # deixe mock até o Passo 3 estar pronto; depois: clickup
CLICKUP_TOKEN=pk_xxxxxxxx
# rede com SSL interceptado (mesmo motivo do --trusted-host no pip):
# "false" ignora a verificação (só nesta máquina confiável) ou aponte pro .pem da CA da empresa.
CLICKUP_VERIFY_SSL=false
```
(atualize também o `.env.example`, sem o valor real)

---

## Passo 3 — Cliente ClickUp + ligar o modo real

Crie **`bff/app/clickup_client.py`** (rascunho):

```python
"""Fonte real das tarefas: ClickUp REST v2. Uma list por área (Personal space)."""
import time
import httpx
from .config import settings

API = "https://api.clickup.com/api/v2"

# área -> list_id (workspace Personal 9007178855, descobertos 2026-07-05)
AREA_LISTS = {
    "Trabalho": "901327729093",
    "Finanças": "901327729095",
    "Saúde":    "901327729097",
    "Pessoal":  "901327729099",
}

def _headers() -> dict:
    # token pessoal ClickUp vai cru no Authorization (sem "Bearer")
    return {"Authorization": settings.clickup_token, "Content-Type": "application/json"}

def _verify():
    """SSL: True normal; False ignora (rede com proxy MITM); ou caminho pro .pem da CA."""
    v = (settings.clickup_verify_ssl or "true").lower()
    if v == "false":
        return False
    if v == "true":
        return True
    return settings.clickup_verify_ssl   # caminho do bundle .pem

def _days_from_ms(ms: str | int | None) -> int | None:
    """Dias de agora até o timestamp (ms). Negativo = passado."""
    if ms in (None, "", 0, "0"):
        return None
    delta_ms = int(ms) - int(time.time() * 1000)
    # arredonda pra baixo em dias “de calendário aproximado”
    return int(delta_ms // 86_400_000)

async def _list_tasks(client: httpx.AsyncClient, list_id: str) -> list[dict]:
    r = await client.get(
        f"{API}/list/{list_id}/task",
        params={"archived": "false", "subtasks": "false", "include_closed": "false"},
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json().get("tasks", [])

async def fetch_open() -> list[dict]:
    """[(area, task_json)] de todas as áreas, só abertas."""
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=30, verify=_verify()) as client:
        for area, lid in AREA_LISTS.items():
            for t in await _list_tasks(client, lid):
                t["_area"] = area
                out.append(t)
    return out

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
    # Descubra com GET /list/{id} -> statuses[]; ajuste "complete" pro nome certo.
    async with httpx.AsyncClient(timeout=30, verify=_verify()) as client:
        r = await client.put(f"{API}/task/{task_id}", json={"status": "complete"}, headers=_headers())
        return r.status_code == 200
```

Agora ligue no **`bff/app/tasks.py`** — troque os `raise NotImplementedError` pelo caminho
ClickUp. Um mapeador `_from_clickup` traduz o JSON do ClickUp pro `_Task` interno (a
cadência em `cadence.py` continua igual):

```python
from . import clickup_client

def _from_clickup(t: dict) -> _Task:
    due = _days_from_clickup(t.get("due_date"))          # ⚠ due_date vem em ms (string)
    updated = clickup_client._days_from_ms(t.get("date_updated"))
    return _Task(
        id=str(t["id"]),
        name=t.get("name", ""),
        area=t["_area"],
        status="open",
        due_offset=due,
        update_offset=(-updated if updated is not None else None),  # dias DESDE o update
        assignee=(t["assignees"][0]["username"] if t.get("assignees") else None),
    )

def _days_from_clickup(ms) -> int | None:
    return clickup_client._days_from_ms(ms)

def _use_clickup() -> bool:
    return settings.tasks_source == "clickup" and bool(settings.clickup_token)
```

E nas quatro funções, troque a guarda:
```python
async def list_by_area() -> dict:
    if not _use_clickup():
        return _grouped(_open())                          # mock
    tasks_ = [_from_clickup(t) for t in await clickup_client.fetch_open()]
    return _grouped(tasks_)

async def create(name: str, area: str) -> Task:
    if not _use_clickup():
        ...  # mock (como está)
    return _from_clickup(await clickup_client.create(name, area))

async def complete(task_id: str) -> bool:
    if not _use_clickup():
        ...  # mock
    return await clickup_client.complete(task_id)

async def run_digest() -> dict:
    src = _open() if not _use_clickup() else [_from_clickup(t) for t in await clickup_client.fetch_open()]
    selected = cadence.select(src)
    ...  # resto igual
```

> Detalhe do `update_offset`: em `_Task`, `days_since_update` = `update_offset`. O ClickUp dá
> `date_updated` no passado, então `update_offset` deve ser **positivo** (dias desde). Por
> isso o `-updated`. `⚠ confirmar no teste` com uma tarefa real.

---

## Passo 4 — Testar

Com o BFF ainda em `TASKS_SOURCE=mock`, rode o cliente isolado pra ver o shape real:

```powershell
# no venv do bff, com CLICKUP_TOKEN no .env
python -c "import asyncio; from app import clickup_client as c; import json; print(json.dumps(asyncio.run(c.fetch_open())[:1], indent=2, ensure_ascii=False))"
```
Olhe **uma** tarefa real e confirme: `due_date` (ms? string?), `date_updated`, `assignees`,
e os nomes de `status`. Ajuste `_from_clickup` e o status de `complete` se preciso.

Aí vire a chave:
```
TASKS_SOURCE=clickup
```
Reinicie o uvicorn e teste os endpoints (pegue o token no `/auth/login`):
```powershell
$tok = (Invoke-RestMethod -Method Post http://localhost:8000/auth/login -ContentType application/json -Body '{"password":"<APP_PASSWORD>"}').token
Invoke-RestMethod http://localhost:8000/tasks  -Headers @{ Authorization = "Bearer $tok" }
Invoke-RestMethod http://localhost:8000/digest -Headers @{ Authorization = "Bearer $tok" }
```
Se vier as tarefas reais agrupadas por área → abra o app e confira Tarefas + Revisão.

---

## Rollback

Qualquer coisa estranha: `TASKS_SOURCE=mock` no `.env` + reiniciar o uvicorn. Volta pro mock
na hora, sem tocar em código.

---

## Depois (não bloqueia)

- **Chat real:** hoje o `Chat.tsx` é mock local. Ligar = cada modo manda pro `/capture` com o
  `profile` certo (Mentor/Conselho/Capturas) e mostra a resposta. Precisa do Hermes de pé.
- **Captura de leitura → vault/ClickUp:** "Compilar sessão" grava os itens (e os ★ Anki) na
  pasta **Livro** (`901310691642`) ou no vault via Hermes.
- **Home real:** os contadores do radar (inbox/vencendo/mentor) viram chamadas ao `/digest`.
