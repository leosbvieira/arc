import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from . import (
    capture_pipeline,
    clickup_client,
    hermes_client,
    push,
    routines,
    store,
    tasks,
    telegram,
    vault_client,
)
from .auth import make_token, require_auth
from .config import settings

logger = logging.getLogger(__name__)


async def _capture_worker() -> None:
    """Worker de fundo da fila de captura (B6/§10): recupera claims órfãos uma vez,
    drena pending_captures em loop e dorme `capture_worker_interval`.

    NUNCA derruba o processo durante uma rodada — process_pending já isola cada item;
    o try aqui cobre falha de infra (ex.: DB), logada SEM conteúdo (lei 7).
    CancelledError é BaseException e escapa do `except Exception` → shutdown limpo.
    """
    store.recover_processing()
    while True:
        try:
            await capture_pipeline.process_pending()
        except Exception:  # noqa: BLE001 - a rodada nunca derruba o loop
            logger.exception("worker de captura: rodada falhou")
        await asyncio.sleep(settings.capture_worker_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    worker = asyncio.create_task(_capture_worker())
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(title="escritório BFF", lifespan=lifespan)


class LoginIn(BaseModel):
    password: str


class TokenOut(BaseModel):
    token: str


class CaptureIn(BaseModel):
    text: str
    profile: str | None = None
    client_key: str | None = None


class CaptureOut(BaseModel):
    reply: str
    queued: bool = False


class SessionIn(BaseModel):
    tipo: Literal["leitura", "foco", "treino", "corrida"] = "leitura"
    livro: str | None = None
    projeto: str | None = None
    paginas: int | None = None
    duracao_s: int
    notas: str = ""


class ChatIn(BaseModel):
    text: str
    mode: str = "Mentor"


class ChatOut(BaseModel):
    reply: str


class DeviceIn(BaseModel):
    token: str


class NotifyIn(BaseModel):
    title: str = "Escritório"
    body: str


class CreateTaskIn(BaseModel):
    name: str
    area: str


class ClosingDraftIn(BaseModel):
    text: str
    template: str = "yoga"


class CheckItem(BaseModel):
    rotina: str
    feito: bool


class ClosingApproveIn(BaseModel):
    raw_text: str
    draft_md: str
    template: str = "yoga"
    checks: list[CheckItem] = []


@app.get("/health")
async def health():
    return {"ok": True, "mock": settings.hermes_mock}


@app.post("/auth/login", response_model=TokenOut)
async def login(body: LoginIn):
    if body.password != settings.app_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "senha incorreta")
    return TokenOut(token=make_token())


@app.post("/capture", response_model=CaptureOut)
async def capture(body: CaptureIn, _: str = Depends(require_auth)):
    """Fire-and-forget (B6): enfileira e responde na hora. O worker processa a fila em
    fundo (Raw → classificação → Staging). O Chat NÃO usa mais esta rota (ela não devolve
    a resposta do Hermes) — conversa síncrona vai por /chat."""
    cid = store.enqueue_capture(body.text, body.profile, body.client_key)
    store.log_event("capture_in", ref=str(cid))
    return CaptureOut(reply="✅ anotado", queued=True)


@app.post("/sessions")
async def create_session(body: SessionIn, _=Depends(require_auth)):
    import time as _t

    fim = _t.time()
    sid = store.add_session(
        body.tipo,
        body.projeto or body.livro,
        body.tipo,
        fim - body.duracao_s,
        fim,
        body.duracao_s,
        body.paginas,
        body.livro,
    )
    raw_path = None
    if body.notas.strip():
        raw_path = await vault_client.write_raw(body.notas, f"s{sid}")
    store.log_event(
        "session_logged",
        ref=str(sid),
        meta={"tipo": body.tipo, "s": body.duracao_s},
    )
    return {"ok": True, "session_id": sid, "raw_path": raw_path}


@app.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, _: str = Depends(require_auth)):
    """Rota síncrona do Chat: fala com o Hermes no modo escolhido e devolve a resposta."""
    try:
        reply = await hermes_client.chat(body.text, body.mode)
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="hermes_indisponivel",
        ) from None
    return ChatOut(reply=reply)


@app.post("/devices")
async def register_device(body: DeviceIn, _: str = Depends(require_auth)):
    store.add_device(body.token)
    return {"ok": True, "count": len(store.list_devices())}


@app.get("/tasks")
async def get_tasks(_: str = Depends(require_auth)):
    return await tasks.list_by_area()


@app.post("/tasks")
async def create_task(body: CreateTaskIn, _: str = Depends(require_auth)):
    if body.area not in tasks.AREAS:
        raise HTTPException(422, f"área inválida; use {tasks.AREAS}")
    t = await tasks.create(body.name, body.area)
    return t.model_dump()


@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str, _: str = Depends(require_auth)):
    ok = await tasks.complete(task_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task não encontrada")
    return {"ok": True}


@app.get("/tasks/{task_id}")
async def get_task_detail(task_id: str, _: str = Depends(require_auth)):
    d = await tasks.get_detail(task_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task não encontrada")
    return d


@app.get("/digest")
async def get_digest(_: str = Depends(require_auth)):
    """Digest do dia pro app. §10: se já rodou hoje, reabre o MESMO corpo persistido
    (body_app) com as tarefas recalculadas frescas p/ a Home; senão, calcula na hora.
    Mantém `count` e `tasks` no shape (compat com o app)."""
    fresh = await tasks.run_digest()
    run = store.get_digest_run(date.today().isoformat())
    if run:
        return {
            "count": run["count"],
            "body": run["body"],
            "tasks": fresh["tasks"],
        }
    return {
        "count": len(fresh["tasks"]),
        "body": fresh["body_app"],
        "tasks": fresh["tasks"],
    }


@app.get("/review/weekly")
async def review_weekly(_=Depends(require_auth)):
    pack = tasks.weekly_review_pack()
    try:
        from datetime import time, timedelta, timezone
        from zoneinfo import ZoneInfo

        local_tz = ZoneInfo("America/Sao_Paulo")
        today = datetime.now(local_tz).date()
        monday = today - timedelta(days=today.weekday())
        monday_local = datetime.combine(
            monday,
            time.min,
            tzinfo=local_tz,
        )
        ts_ms = int(
            monday_local.astimezone(timezone.utc).timestamp() * 1000,
        )
        pack["tarefas_concluidas"] = (
            await clickup_client.count_closed_since(ts_ms)
        )
        pack["staging_pendentes"] = await clickup_client.count_open(
            clickup_client.AREA_LISTS[clickup_client.STAGING],
        )
    except Exception:
        pass
    return pack


@app.get("/closing/routines")
async def closing_routines(template: str = "yoga", _=Depends(require_auth)):
    return {"routines": routines.ROUTINES.get(template, routines.ROUTINES["yoga"])}


@app.post("/closing/draft")
async def closing_draft(body: ClosingDraftIn, _=Depends(require_auth)):
    return {"draft": await hermes_client.draft_diario(body.text, body.template)}


@app.post("/closing/approve")
async def closing_approve(body: ClosingApproveIn, _=Depends(require_auth)):
    import hashlib

    today = date.today().isoformat()
    raw_path = await vault_client.write_raw(
        body.raw_text,
        f"f{today.replace('-', '')}",
    )
    marker = (
        f"<!-- fechamento:{today}:"
        f"{hashlib.sha1(body.draft_md.encode()).hexdigest()[:8]} -->"
    )
    block = (
        f"## Fechamento ({datetime.now():%H:%M}) {marker}\n\n"
        f"{body.draft_md}\n\n_raw: [[{raw_path}]]_\n"
    )
    daily_path = await vault_client.append_file(
        f"Daily/{today}.md",
        block,
        f"diario: fechamento {today}",
        header_if_new=f"# {today}",
        dedupe_marker=marker,
    )
    store.record_checks(
        today,
        body.template,
        [(c.rotina, c.feito) for c in body.checks],
    )
    store.log_event("closing_approved", ref=today)
    return {"ok": True, "daily_path": daily_path, "raw_path": raw_path}


def _check_internal(token: str) -> None:
    if token != settings.internal_token:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "token interno inválido",
        )


@app.post("/internal/notify")
async def internal_notify(
    body: NotifyIn,
    x_internal_token: str = Header(default=""),
):
    _check_internal(x_internal_token)
    return await push.send_push(
        store.list_devices(),
        body.title,
        body.body,
    )


@app.post("/internal/run-digest")
async def internal_run_digest(x_internal_token: str = Header(default="")):
    """Calcula e ENTREGA o digest do dia pelo Telegram (C10/C11). 1/dia por ENTREGA real:
    falha de envio NÃO consome o slot do dia (retry same-day permitido, §10). Persiste o
    run pro app reabrir (body neutralizado só no Telegram; body_app tem tudo)."""
    _check_internal(x_internal_token)
    today = date.today().isoformat()
    if store.notif_sent_today("digest"):
        return {"skipped": "digest ja enviado hoje"}
    result = await tasks.run_digest()
    has_content = bool(result["tasks"]) or bool(result.get("lines_extra"))
    delivered = False
    if has_content:
        delivered = await telegram.send(result["body_telegram"])
        store.log_notif("digest", "telegram", delivered)
    store.save_digest_run(
        today,
        result["body_app"],
        len(result["tasks"]),
        delivered,
    )
    return {"count": len(result["tasks"]), "telegram": delivered}
