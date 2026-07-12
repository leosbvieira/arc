import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, field_validator

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
from .config import DEFAULTS, settings

logger = logging.getLogger(__name__)

NUDGE_COPY = {
    "closing": "21h — fechar o dia? 90 segundos bastam: 1 linha + checks.",
    "review": "domingo 20h — review semanal. Os números da semana te esperam no app.",
}


def _guard_default_secrets() -> None:
    if any(
        getattr(settings, field) == default
        for field, default in DEFAULTS.items()
    ):
        raise RuntimeError("segredos default detectados — configure o .env")


async def _capture_worker() -> None:
    """Worker de fundo da fila de captura (B6/§10): recupera claims órfãos e
    reapresenta failed uma vez no startup, drena pending_captures em loop e
    dorme `capture_worker_interval`.

    NUNCA derruba o processo durante uma rodada — process_pending já isola cada item;
    os try aqui cobrem falha de infra (ex.: DB), logada SEM conteúdo (lei 7).
    CancelledError é BaseException e escapa do `except Exception` → shutdown limpo.
    """
    try:
        store.recover_processing()
    except Exception:  # noqa: BLE001 - recuperação não derruba o worker
        logger.exception("worker de captura: recuperação de processing falhou")

    try:
        store.retry_failed_captures()
    except Exception:  # noqa: BLE001 - reapresentação não derruba o worker
        logger.exception("worker de captura: reapresentação de failed falhou")

    while True:
        try:
            await capture_pipeline.process_pending()
        except Exception:  # noqa: BLE001 - a rodada nunca derruba o loop
            logger.exception("worker de captura: rodada falhou")
        await asyncio.sleep(settings.capture_worker_interval)


async def fire_due_schedules() -> None:
    import time as _t

    for item in store.due_schedules(_t.time()):
        ok = False
        try:
            ok = await telegram.send(f"⏰ {item['ref']}")
            if ok:
                store.mark_schedule_fired(item["id"])
        except Exception:  # noqa: BLE001 - um item ruim não aborta o tick
            logger.exception("scheduler: item falhou")

        try:
            store.log_notif("hora_marcada", "telegram", ok)
        except Exception:  # noqa: BLE001 - um log ruim não aborta os demais itens
            logger.exception("scheduler: log de notificação falhou")


async def _scheduler_worker() -> None:
    # Scheduler não usa recover: horários vencidos enquanto o PC estava desligado
    # são retornados por due_schedules(quando <= agora) no próximo tick do worker.
    while True:
        try:
            await fire_due_schedules()
        except Exception:  # noqa: BLE001 - a rodada nunca derruba o loop
            logger.exception("scheduler")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _guard_default_secrets()
    store.init_db()
    worker = asyncio.create_task(_capture_worker())
    scheduler = asyncio.create_task(_scheduler_worker())
    try:
        yield
    finally:
        worker.cancel()
        scheduler.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        with suppress(asyncio.CancelledError):
            await scheduler


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
    session_key: str | None = None


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


class NudgeIn(BaseModel):
    kind: Literal["closing", "review"]


# --- rotinas (dado editável; P2 item 2) -------------------------------------
# Os validadores normalizam a entrada do app e falham fechado (422) em bloco/dia/
# template inválido. `slug` NUNCA vem do app: é derivado do nome no create e, depois
# disso, é imutável — ele é a chave que amarra o histórico em routine_checks.


class RoutineIn(BaseModel):
    nome: str
    bloco: str
    dias: str = "*"
    templates: str = "*"
    passos: list[str] = []

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nome vazio")
        return v.strip()

    @field_validator("bloco")
    @classmethod
    def _bloco(cls, v: str) -> str:
        return routines.norm_bloco(v)

    @field_validator("dias")
    @classmethod
    def _dias(cls, v: str) -> str:
        return routines.norm_dias(v)

    @field_validator("templates")
    @classmethod
    def _templates(cls, v: str) -> str:
        return routines.norm_templates(v)

    @field_validator("passos")
    @classmethod
    def _passos(cls, v: list[str]) -> list[str]:
        return routines.norm_passos(v)


class RoutinePatch(BaseModel):
    """Patch parcial. Campos ausentes ficam como estão (model_dump(exclude_unset)).
    `slug` no body é ignorado de propósito — não é um campo aqui."""

    nome: str | None = None
    bloco: str | None = None
    dias: str | None = None
    templates: str | None = None
    passos: list[str] | None = None
    ordem: int | None = None

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not v.strip():
            raise ValueError("nome vazio")
        return v.strip()

    @field_validator("bloco")
    @classmethod
    def _bloco(cls, v: str | None) -> str | None:
        return routines.norm_bloco(v) if v is not None else None

    @field_validator("dias")
    @classmethod
    def _dias(cls, v: str | None) -> str | None:
        return routines.norm_dias(v) if v is not None else None

    @field_validator("templates")
    @classmethod
    def _templates(cls, v: str | None) -> str | None:
        return routines.norm_templates(v) if v is not None else None

    @field_validator("passos")
    @classmethod
    def _passos(cls, v: list[str] | None) -> list[str] | None:
        return routines.norm_passos(v) if v is not None else None


class ReorderItem(BaseModel):
    id: int
    ordem: int


class ReorderIn(BaseModel):
    ordem: list[ReorderItem]


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


@app.post("/captures/retry-failed")
async def retry_failed_captures(_: str = Depends(require_auth)):
    return {"requeued": store.retry_failed_captures()}


@app.post("/sessions")
async def create_session(body: SessionIn, _=Depends(require_auth)):
    import time as _t

    fim = _t.time()
    inicio = fim - body.duracao_s
    result = store.add_session(
        body.tipo,
        body.projeto or body.livro,
        body.tipo,
        inicio,
        fim,
        body.duracao_s,
        body.paginas,
        body.livro,
        return_created=True,
        session_key=body.session_key,
    )
    sid, created = result

    if not created:
        inicio = store.get_session_inicio(sid)

    raw_path = None
    if body.notas.strip():
        raw_path = await vault_client.write_raw(
            body.notas,
            f"s{sid}",
            ts=inicio,
        )

    if not created:
        return {"ok": True, "session_id": sid, "raw_path": raw_path}

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


# --- rotinas: CRUD (a tela de Rotinas do app) --------------------------------


@app.get("/routines")
async def list_routines(_=Depends(require_auth)):
    return {"routines": store.list_routines()}


@app.post("/routines")
async def create_routine(body: RoutineIn, _=Depends(require_auth)):
    return (
        store.create_routine(
            body.nome,
            body.bloco,
            body.dias,
            body.templates,
            body.passos,
        )
    )


@app.patch("/routines/{routine_id}")
async def patch_routine(
    routine_id: int,
    body: RoutinePatch,
    _=Depends(require_auth),
):
    campos = body.model_dump(exclude_unset=True, exclude_none=True)
    r = store.update_routine(routine_id, **campos)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rotina não encontrada")
    return r


@app.delete("/routines/{routine_id}")
async def delete_routine(routine_id: int, _=Depends(require_auth)):
    """Soft delete: some da lista e do fechamento, mas os checks já gravados (que
    referenciam o slug) continuam contando no scorecard das semanas passadas."""
    if not store.delete_routine(routine_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rotina não encontrada")
    return {"ok": True}


@app.post("/routines/reorder")
async def reorder_routines(body: ReorderIn, _=Depends(require_auth)):
    n = store.reorder_routines([(i.id, i.ordem) for i in body.ordem])
    return {"ok": True, "updated": n}


@app.get("/closing/routines")
async def closing_routines(
    template: str = "yoga",
    dia: str | None = Query(default=None, alias="date"),
    _=Depends(require_auth),
):
    """Só o que vale NAQUELE dia: filtra por dia da semana + template + ativo.

    Devolve objetos (antes eram strings): o app precisa do `slug` (chave dos checks),
    do `bloco` (a manhã não aparece no fechamento das 21h) e dos `passos` (roteiro —
    NÃO são checks; quem conta no scorecard é o item pai)."""
    try:
        ref = date.fromisoformat(dia) if dia else date.today()
    except ValueError:
        raise HTTPException(422, "date inválida; use YYYY-MM-DD") from None
    do_dia = routines.do_dia(store.list_routines(), ref, template)
    return {
        "routines": [
            {k: r[k] for k in ("id", "slug", "nome", "bloco", "passos")}
            for r in do_dia
        ]
    }


@app.post("/closing/draft")
async def closing_draft(body: ClosingDraftIn, _=Depends(require_auth)):
    return {"draft": await hermes_client.draft_diario(body.text, body.template)}


@app.post("/closing/approve")
async def closing_approve(body: ClosingApproveIn, _=Depends(require_auth)):
    import hashlib

    today = date.today().isoformat()
    raw_hash = hashlib.sha1(body.raw_text.encode("utf-8")).hexdigest()[:8]
    raw_path = await vault_client.write_raw(
        body.raw_text,
        f"f{today}-{raw_hash}",
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


@app.post("/internal/nudge")
async def internal_nudge(
    body: NudgeIn,
    x_internal_token: str = Header(""),
):
    _check_internal(x_internal_token)
    if store.notif_sent_today(f"nudge_{body.kind}"):
        return {"skipped": True}
    text = NUDGE_COPY[body.kind]
    if body.kind == "review":
        try:
            text = text + "\n\n" + tasks.weekly_review_text()
        except Exception:
            pass
    delivered = await telegram.send(text)
    store.log_notif(f"nudge_{body.kind}", "telegram", delivered)
    return {"ok": True, "telegram": delivered}


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
