import asyncio
import logging
import re
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from datetime import date, datetime, time as _time, timedelta
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, field_validator

from . import (
    agenda,
    anki,
    capture_pipeline,
    clickup_client,
    google_calendar,
    hermes_client,
    notify,
    objetivos,
    pontos,
    routines,
    store,
    tasks,
    vault_client,
)
from .auth import make_token, require_auth
from .config import DEFAULTS, settings

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Sao_Paulo")

# Tom: seco e factual (lei 4 — o sistema não motiva, não envergonha; diz o fato e o custo).
NUDGE_COPY = {
    "toque": "5h30 — dia yoga ou dia corrida?",
    "checkin": "8h20 — check-in: energia, clareza, prioridade nº1. 60 segundos.",
    "jornal": "8h30 — jornal de leitura de notícias. Abra Capturar para iniciar.",
    "shutdown": "19h — Shutdown: fechar o trabalho, follow-ups, 3 prioridades de amanhã.",
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
    """O ⏰ da hora marcada. Sai pela camada única (notify): push primeiro, Telegram de
    ponte. Quem loga em `notif_log` é o `notificar` — o canal REAL usado."""
    import time as _t

    for item in store.due_schedules(_t.time()):
        try:
            entrega = await notify.notificar("hora_marcada", f"⏰ {item['ref']}")
            if entrega["push"] or entrega["telegram"]:
                store.mark_schedule_fired(item["id"])
        except Exception:  # noqa: BLE001 - um item ruim não aborta o tick
            logger.exception("scheduler: item falhou")


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
    sensivel: bool = False


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


class ReadingSessionIn(BaseModel):
    model_config = {"extra": "forbid"}

    client_key: str
    livro: str
    pagina_inicial: int | None = None
    inicio: float | None = None

    @field_validator("client_key", "livro")
    @classmethod
    def validar_texto_obrigatorio(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("campo vazio")
        return value

    @field_validator("pagina_inicial", mode="before")
    @classmethod
    def validar_pagina(cls, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("pagina_inicial inválida")
        return value


class ReadingBufferIn(BaseModel):
    model_config = {"extra": "forbid"}

    seq: int
    hook: Literal["quote", "comentario", "ideia", "coach", "lista", "texto"] = "texto"
    texto: str
    ts: float | None = None

    @field_validator("seq", mode="before")
    @classmethod
    def validar_seq(cls, value):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("seq deve ser inteiro positivo")
        return value

    @field_validator("texto")
    @classmethod
    def validar_texto(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("texto vazio")
        return value


class ReadingCompileIn(BaseModel):
    model_config = {"extra": "forbid"}

    pagina_final: int | None = None
    fim: float | None = None

    @field_validator("pagina_final", mode="before")
    @classmethod
    def validar_pagina(cls, value):
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("pagina_final inválida")
        return value


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
    kind: str = "manual_notify"
    sensivel: bool = False

    @field_validator("kind")
    @classmethod
    def validar_kind(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[a-z0-9_-]{1,64}", value):
            raise ValueError("kind inválido")
        return value


class CreateTaskIn(BaseModel):
    name: str
    area: str
    due: str | None = None
    hora: str | None = None

    @field_validator("due")
    @classmethod
    def validar_due(cls, valor: str | None) -> str | None:
        """Falha fechado: uma data ambígua não pode criar cobrança no dia errado."""
        if valor is None:
            return None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            raise ValueError("due inválido; use YYYY-MM-DD")
        try:
            date.fromisoformat(valor)
        except ValueError:
            raise ValueError("due inválido; use YYYY-MM-DD") from None
        return valor

    @field_validator("hora")
    @classmethod
    def validar_hora(cls, valor: str | None) -> str | None:
        """Aceita somente hora civil explícita para o scheduler não precisar adivinhar."""
        if valor is None:
            return None
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", valor):
            raise ValueError("hora inválida; use HH:MM")
        return valor


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
    kind: Literal["toque", "checkin", "jornal", "shutdown", "closing", "review"]


# --- o dia (A1a toque 5h30 + A1b check-in 8h20) e o Shutdown (A2, 19h) -------
# `data` é opcional em todos: o app normalmente não manda (é sempre hoje), mas o campo
# existe pra corrigir o dia anterior sem depender do relógio do servidor.


class DiaTemplateIn(BaseModel):
    template: Literal["yoga", "corrida"]
    data: str | None = None


class CheckinIn(BaseModel):
    energia: Literal["baixa", "media", "alta"]
    clareza: Literal["baixa", "media", "alta"]
    prioridade_1: str = ""
    data: str | None = None

    @field_validator("prioridade_1")
    @classmethod
    def _prioridade(cls, v: str) -> str:
        return v.strip()


class RoutineCheckIn(BaseModel):
    slug: str
    feito: bool
    data: str | None = None


class ShutdownIn(BaseModel):
    prioridades: list[str] = []

    @field_validator("prioridades")
    @classmethod
    def _prioridades(cls, v: list[str]) -> list[str]:
        limpas = [p.strip() for p in v if p and p.strip()]
        if len(limpas) > 3:
            raise ValueError("máximo 3 prioridades")
        return limpas


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


class ObjetivoCreateIn(BaseModel):
    model_config = {"extra": "forbid"}

    nome: str
    rotina_slug: str | None = None
    alvo_semana: int | None = None

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        nome = valor.strip()
        if not nome:
            raise ValueError("nome não pode ser vazio")
        return nome

    @field_validator("rotina_slug")
    @classmethod
    def validar_rotina_slug(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        slug = valor.strip()
        if not slug:
            raise ValueError("rotina_slug não pode ser vazio")
        return slug

    @field_validator("alvo_semana", mode="before")
    @classmethod
    def validar_alvo(cls, valor):
        if valor is None:
            return None
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError("alvo_semana deve ser inteiro")
        if not 1 <= valor <= 7:
            raise ValueError("alvo_semana deve estar entre 1 e 7")
        return valor


class ObjetivoPatchIn(BaseModel):
    model_config = {"extra": "forbid"}

    nome: str | None = None
    alvo_semana: int | None = None

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str | None) -> str | None:
        if valor is None:
            raise ValueError("nome não pode ser nulo")
        nome = valor.strip()
        if not nome:
            raise ValueError("nome não pode ser vazio")
        return nome

    @field_validator("alvo_semana", mode="before")
    @classmethod
    def validar_alvo(cls, valor):
        # null remove o alvo semanal; ausência mantém o valor atual.
        if valor is None:
            return None
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError("alvo_semana deve ser inteiro")
        if not 1 <= valor <= 7:
            raise ValueError("alvo_semana deve estar entre 1 e 7")
        return valor


class ObjetivoMarcaIn(BaseModel):
    model_config = {"extra": "forbid"}

    data: str | None = None


class MovimentoIn(BaseModel):
    model_config = {"extra": "forbid"}

    task_id: str
    area: str

    @field_validator("area")
    @classmethod
    def validar_area_triavel(cls, value: str) -> str:
        """Aceita apenas destinos reais; Staging não é destino de triagem."""
        if value not in tasks.AREAS or value == "Staging":
            raise ValueError("area inválida para triagem")
        return value


class TriagemAplicarIn(BaseModel):
    model_config = {"extra": "forbid"}

    movimentos: list[MovimentoIn]

    @field_validator("movimentos")
    @classmethod
    def validar_movimentos_nao_vazios(
        cls,
        value: list[MovimentoIn],
    ) -> list[MovimentoIn]:
        """Exige aprovação explícita de pelo menos um movimento."""
        if not value:
            raise ValueError("movimentos não pode ser vazio")
        return value


class AnkiSugerirIn(BaseModel):
    model_config = {"extra": "forbid"}

    notas: str
    session_id: int | None = None

    @field_validator("notas")
    @classmethod
    def validar_notas(cls, value: str) -> str:
        """Recusa sessão sem matéria-prima para manter a sugestão fail-closed."""
        value = value.strip()
        if not value:
            raise ValueError("notas não pode ser vazio")
        return value


class AnkiCardPatchIn(BaseModel):
    model_config = {"extra": "forbid"}

    frente: str | None = None
    meaning: str | None = None
    example: str | None = None
    hook: str | None = None
    deck: str | None = None
    status: str | None = None

    @field_validator("frente", "meaning", "example", "hook", "deck")
    @classmethod
    def validar_campos_textuais(cls, value: str | None) -> str:
        """Diferencia campo omitido de nulo explícito para preservar o banco."""
        if value is None:
            raise ValueError("campo não pode ser nulo")
        return value

    @field_validator("status")
    @classmethod
    def validar_status(cls, value: str | None) -> str:
        """Reserva exportado ao fluxo atômico; a IA nunca toma essa decisão."""
        if value not in {"sugerido", "aprovado", "descartado"}:
            raise ValueError("status_anki_invalido")
        return value


class TemaIn(BaseModel):
    texto: str
    semana: str | None = None

    @field_validator("texto")
    @classmethod
    def validar_texto(cls, valor: str) -> str:
        """Tema vazio não cria lembrete sem informação, conforme a lei 4."""
        texto = valor.strip()
        if not texto:
            raise ValueError("texto não pode ser vazio")
        return texto

    @field_validator("semana")
    @classmethod
    def validar_semana(cls, valor: str | None) -> str | None:
        """A chave explícita evita gravar o tema em uma semana inferida incorretamente."""
        if valor is not None and not re.fullmatch(r"\d{4}-W\d{2}", valor):
            raise ValueError("semana inválida; use YYYY-Www")
        return valor


class GoogleCalendarEventIn(BaseModel):
    model_config = {"extra": "forbid"}

    titulo: str
    data: str
    hora: str
    duracao_min: int = 60
    client_key: str

    @field_validator("titulo")
    @classmethod
    def validar_titulo(cls, valor: str) -> str:
        titulo = valor.strip()
        if not titulo:
            raise ValueError("titulo não pode ser vazio")
        if len(titulo) > 200:
            raise ValueError("titulo excede 200 caracteres")
        return titulo

    @field_validator("data")
    @classmethod
    def validar_data(cls, valor: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            raise ValueError("data inválida; use YYYY-MM-DD")
        try:
            date.fromisoformat(valor)
        except ValueError:
            raise ValueError("data inválida; use YYYY-MM-DD") from None
        return valor

    @field_validator("hora")
    @classmethod
    def validar_hora(cls, valor: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", valor):
            raise ValueError("hora inválida; use HH:MM")
        return valor

    @field_validator("duracao_min", mode="before")
    @classmethod
    def validar_duracao(cls, valor):
        if isinstance(valor, bool) or not isinstance(valor, int):
            raise ValueError("duracao_min deve ser inteiro")
        if not 5 <= valor <= 720:
            raise ValueError("duracao_min deve estar entre 5 e 720")
        return valor

    @field_validator("client_key")
    @classmethod
    def validar_client_key(cls, valor: str) -> str:
        chave = valor.strip()
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,160}", chave):
            raise ValueError("client_key inválida")
        return chave


def _semana_tema(valor: str | None) -> str:
    """Valida a query com o mesmo contrato fail-closed usado pelo modelo."""
    if valor is None:
        return agenda.semana_iso(date.today())
    if not re.fullmatch(r"\d{4}-W\d{2}", valor):
        raise HTTPException(422, "semana inválida; use YYYY-Www")
    return valor


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
    cid = store.enqueue_capture(
        body.text,
        body.profile,
        body.client_key,
        sensivel=body.sensivel,
    )
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


def _reading_notes(session: dict) -> str:
    """Serializa hooks sem alterar o texto; é matéria-prima local, nunca log."""
    return "\n".join(
        f"{chunk['hook']}: {chunk['texto']}"
        for chunk in session.get("buffer", [])
    )


async def _suggest_anki_once(session_id: int, notas: str) -> list[dict]:
    state = store.claim_anki_suggestion(session_id)
    if state == "done":
        return store.list_anki_cards_for_session(session_id)
    if state == "processing":
        raise RuntimeError("anki_suggestion_em_andamento")
    try:
        candidatos = await hermes_client.suggest_anki(notas)
        return store.finish_anki_suggestion(session_id, candidatos)
    except Exception:
        store.release_anki_suggestion(session_id)
        raise


@app.post("/reading/sessions")
async def create_reading_session(
    body: ReadingSessionIn,
    _auth: None = Depends(require_auth),
):
    session, created = store.create_reading_session(
        body.client_key,
        body.livro,
        pagina_inicial=body.pagina_inicial,
        inicio=body.inicio,
    )
    if created:
        store.log_event("reading_started", ref=str(session["id"]))
    return {"session": session, "created": created}


@app.post("/reading/sessions/{session_id}/buffer")
async def autosave_reading_buffer(
    session_id: int,
    body: ReadingBufferIn,
    _auth: None = Depends(require_auth),
):
    try:
        chunk, created = store.append_reading_buffer(
            session_id,
            body.seq,
            body.hook,
            body.texto,
            ts=body.ts,
        )
    except LookupError:
        raise HTTPException(404, "reading_session_nao_encontrada") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if created:
        store.log_event(
            "reading_autosaved",
            ref=str(session_id),
            meta={"seq": body.seq, "hook": body.hook},
        )
    return {"chunk": chunk, "created": created}


@app.get("/reading/sessions/pending")
async def pending_reading_sessions(_auth: None = Depends(require_auth)):
    return {"sessions": store.list_pending_reading_sessions()}


@app.post("/reading/sessions/{session_id}/compile")
async def compile_reading_session(
    session_id: int,
    body: ReadingCompileIn,
    _auth: None = Depends(require_auth),
):
    import time as _t

    state, session = store.claim_reading_compile(session_id)
    if state == "missing":
        raise HTTPException(404, "reading_session_nao_encontrada")
    if state == "discarded":
        raise HTTPException(409, "reading_session_descartada")
    if state == "compiling":
        raise HTTPException(409, "reading_compile_em_andamento")
    if state == "empty":
        raise HTTPException(422, "reading_buffer_vazio")

    if state == "compiled":
        cards: list[dict] = []
        anki_status = "pending"
        if session.get("compiled_session_id"):
            try:
                cards = await _suggest_anki_once(
                    int(session["compiled_session_id"]),
                    _reading_notes(session),
                )
                anki_status = "done"
                session = store.purge_reading_content(session_id)
            except Exception:
                # Anki é best-effort e nunca reabre uma compilação já publicada.
                pass
        return {
            "session": session,
            "anki_cards": cards,
            "anki_status": anki_status,
        }

    assert state == "claimed" and session is not None
    fim = _t.time() if body.fim is None else float(body.fim)
    if fim < float(session["inicio"]):
        store.release_reading_compile(session_id, "fim_antes_do_inicio")
        raise HTTPException(422, "fim_antes_do_inicio")
    if (
        body.pagina_final is not None
        and session.get("pagina_inicial") is not None
        and body.pagina_final < int(session["pagina_inicial"])
    ):
        store.release_reading_compile(session_id, "pagina_final_invalida")
        raise HTTPException(422, "pagina_final_invalida")

    try:
        draft = session.get("draft_md")
        if not draft:
            draft = await hermes_client.compile_reading(
                session["livro"],
                session["buffer"],
                pagina_inicial=session.get("pagina_inicial"),
                pagina_final=body.pagina_final,
            )
            store.save_reading_draft(session_id, draft)

        vault_path = await vault_client.write_reading_note(
            draft,
            session_id,
            ts=float(session["inicio"]),
            client_key=session["client_key"],
        )
        paginas = None
        if body.pagina_final is not None and session.get("pagina_inicial") is not None:
            paginas = body.pagina_final - int(session["pagina_inicial"])
        compiled_session_id, created = store.add_session(
            "leitura",
            session["livro"],
            "leitura",
            float(session["inicio"]),
            fim,
            max(0, round(fim - float(session["inicio"]))),
            paginas,
            session["livro"],
            return_created=True,
            session_key=f"reading:{session_id}",
        )
        compiled = store.finish_reading_compile(
            session_id,
            vault_path=vault_path,
            compiled_session_id=compiled_session_id,
            pagina_final=body.pagina_final,
            fim=fim,
        )
    except Exception as exc:
        store.release_reading_compile(session_id, type(exc).__name__)
        store.log_event(
            "reading_compile_failed",
            ref=str(session_id),
            meta={"error": type(exc).__name__},
        )
        raise HTTPException(502, "reading_compile_indisponivel") from None

    if created:
        store.log_event(
            "session_logged",
            ref=str(compiled_session_id),
            meta={"tipo": "leitura", "s": max(0, round(fim - float(session["inicio"])))},
        )
    store.log_event("reading_compiled", ref=str(session_id))

    cards: list[dict] = []
    anki_status = "pending"
    try:
        cards = await _suggest_anki_once(
            compiled_session_id,
            _reading_notes(compiled),
        )
        anki_status = "done"
        compiled = store.purge_reading_content(session_id)
    except Exception as exc:
        store.log_event(
            "anki_suggestion_failed",
            ref=str(compiled_session_id),
            meta={"error": type(exc).__name__},
        )
    return {
        "session": compiled,
        "anki_cards": cards,
        "anki_status": anki_status,
    }


@app.post("/reading/sessions/{session_id}/discard")
async def discard_reading_session(
    session_id: int,
    _auth: None = Depends(require_auth),
):
    state, session = store.discard_reading_session(session_id)
    if state == "missing":
        raise HTTPException(404, "reading_session_nao_encontrada")
    if state not in {"discarded"}:
        raise HTTPException(409, f"reading_session_{state}")
    store.log_event("reading_discarded", ref=str(session_id))
    return {"session": session}


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
    due_ref = (
        date.fromisoformat(body.due)
        if body.due
        else date.today() if body.hora else None
    )
    com_hora = body.hora is not None
    due_ts = None
    if due_ref is not None:
        horario = _time.fromisoformat(body.hora) if body.hora else _time.min
        due_ts = datetime.combine(due_ref, horario, tzinfo=TZ).timestamp()

    t = await tasks.create(
        body.name,
        body.area,
        due_ts=due_ts,
        com_hora=com_hora,
    )
    if com_hora:
        # O ref chega à lockscreen; área sensível nunca carrega o nome, conforme a lei 7.
        ref_txt = body.name if not tasks.eh_sensivel(body.area) else tasks.NEUTRO
        store.add_schedule(due_ts, "minha", ref_txt)
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


@app.get("/pontos")
async def get_pontos(_=Depends(require_auth)):
    """Pontos + Conquistas N1-4 (P2 item 3). Só LEITURA: o placar é uma função pura de
    `routine_checks` + config (pontos.py), nunca um saldo mutável — não há rota que
    escreva ponto, e não pode haver. Quem move o número é o fechamento do dia."""
    return pontos.resumo()


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


@app.get("/review/monthly")
async def review_monthly(_=Depends(require_auth)):
    pack = tasks.monthly_review_pack()
    try:
        from datetime import time, timedelta, timezone
        from zoneinfo import ZoneInfo

        local_tz = ZoneInfo("America/Sao_Paulo")
        today = datetime.now(local_tz).date()
        inicio_mes_atual = today.replace(day=1)
        fim_mes_anterior = inicio_mes_atual - timedelta(days=1)
        inicio_mes_anterior = fim_mes_anterior.replace(day=1)
        inicio_local = datetime.combine(
            inicio_mes_anterior,
            time.min,
            tzinfo=local_tz,
        )
        ts_ms = int(
            inicio_local.astimezone(timezone.utc).timestamp() * 1000,
        )

        fim_ms = int(
            datetime.combine(
                inicio_mes_atual,
                time.min,
                tzinfo=local_tz,
            ).astimezone(timezone.utc).timestamp()
            * 1000
        )
        pack["tarefas_concluidas"] = await clickup_client.count_closed_between(
            ts_ms,
            fim_ms,
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


# --- o dia: abertura (A1a + A1b) e o check avulso de rotina ------------------
# O buraco que isto fecha: o template de dia ("dia yoga / dia corrida") já existia em
# código, mas só aparecia na tela de FECHAMENTO das 21h — o Leo marcava "acordar 5h30"
# à noite, retroativamente. A abertura traz o template pra manhã, onde ele é decisão;
# o POST /routines/check permite marcar UMA rotina na hora em que ela acontece.


def _data_ref(valor: str | None) -> date:
    """`data` opcional (YYYY-MM-DD) → date. Ausente = hoje. Inválida = 422 (fail-closed:
    não se chuta um dia; escrever no dia errado corromperia o histórico do scorecard)."""
    try:
        return date.fromisoformat(valor) if valor else date.today()
    except (TypeError, ValueError):
        raise HTTPException(422, "data inválida; use YYYY-MM-DD") from None


def _template_do_dia(data: str) -> str | None:
    dia = store.get_dia(data)
    return dia["template"] if dia else None


@app.post("/dia/template")
async def dia_template(body: DiaTemplateIn, _=Depends(require_auth)):
    """O toque das 5h30 (A1a): ele responde qual é o dia. Idempotente — e não apaga o
    check-in de 8h20 se por algum motivo o toque vier depois."""
    ref = _data_ref(body.data)
    dia = store.set_dia_template(ref.isoformat(), body.template)
    store.log_event("dia_template", ref=ref.isoformat(), meta={"t": body.template})
    return {"ok": True, "dia": dia}


@app.get("/abertura")
async def abertura(
    dia: str | None = Query(default=None, alias="data"),
    _=Depends(require_auth),
):
    """O pack da manhã. Junta as 4 coisas que ele precisa ver antes de começar o dia:
    o template escolhido, as rotinas da MANHÃ (com o que já está marcado), o que o
    Shutdown de ontem deixou planejado, e o que hoje cobra (tarefas + hora marcada)."""
    ref = _data_ref(dia)
    data = ref.isoformat()
    linha = store.get_dia(data)
    template = linha["template"] if linha else None

    checks = store.get_checks_on(data)
    rotinas_manha = [
        {
            "id": r["id"],
            "slug": r["slug"],
            "nome": r["nome"],
            "passos": r["passos"],
            "feito": checks.get(r["slug"], False),
        }
        for r in routines.do_dia(store.list_routines(), ref, template)
        if r["bloco"] == "manha"
    ]

    ontem = store.get_shutdown((ref - timedelta(days=1)).isoformat())

    # `due_hoje` é relativo a HOJE (o due vem do ClickUp em dias até vencer). Pedir a
    # abertura de outro dia devolve o estado daquele dia, mas não reescreve o calendário.
    tarefas_due = await tasks.due_hoje() if ref == date.today() else []

    temas = store.list_temas(agenda.semana_iso(ref))
    calendario: list[dict] = []
    fontes_calendario = {"gcal": "erro", "outlook": "erro"}
    try:
        agenda_dia = await agenda.do_dia(ref, incluir_hora_marcada=False)
        calendario = agenda_dia["eventos"]
        fontes_calendario = agenda_dia["fontes"]
        temas = agenda_dia["temas"]
    except Exception:  # noqa: BLE001 - a abertura não depende de uma fonte externa
        # Degrada com estado explícito e preserva a pauta local, conforme a lei 4.
        logger.exception("abertura: agenda externa indisponível")

    inicio = datetime.combine(ref, _time.min, tzinfo=TZ).timestamp()
    fim = datetime.combine(ref + timedelta(days=1), _time.min, tzinfo=TZ).timestamp()
    horarios = [
        {
            "hora": datetime.fromtimestamp(item["quando"], TZ).strftime("%H:%M"),
            "ref": item["ref"],
        }
        for item in store.schedules_between(inicio, fim)
    ]

    return {
        "data": data,
        "template": template,
        "rotinas_manha": rotinas_manha,
        "prioridades_de_ontem": ontem["prioridades"] if ontem else [],
        "temas": temas,
        "hoje": {
            "tarefas_due": tarefas_due,
            "horarios": horarios,
            "calendario": calendario,
            "fontes_calendario": fontes_calendario,
        },
        "checkin": {
            "feito": bool(linha and linha["checkin_em"]),
            "energia": linha["energia"] if linha else None,
            "clareza": linha["clareza"] if linha else None,
            "prioridade_1": linha["prioridade_1"] if linha else None,
        },
    }


@app.post("/abertura/checkin")
async def abertura_checkin(body: CheckinIn, _=Depends(require_auth)):
    """O check-in das 8h20 (A1b): estado (energia/clareza) + a prioridade nº1 do dia."""
    ref = _data_ref(body.data)
    dia = store.set_checkin(
        ref.isoformat(),
        body.energia,
        body.clareza,
        body.prioridade_1,
    )
    store.log_event("checkin", ref=ref.isoformat())
    return {"ok": True, "dia": dia}


@app.post("/routines/check")
async def check_routine(body: RoutineCheckIn, _=Depends(require_auth)):
    """Marca UMA rotina, a qualquer hora do dia — é isto que quebra o "marcar 5h30 às 21h".

    O `template` da linha vem da tabela `dia`; se o toque das 5h30 ainda não veio, grava
    com 'yoga' (o default). Escrita parcial: a PK (data, rotina) deixa esta linha conviver
    com o que o fechamento das 21h gravar depois — e o fechamento NÃO apaga esta aqui.
    """
    ref = _data_ref(body.data)
    data = ref.isoformat()
    if not any(r["slug"] == body.slug for r in store.list_routines()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "rotina não encontrada")

    template = _template_do_dia(data) or "yoga"
    store.record_checks(data, template, [(body.slug, body.feito)])
    return {
        "ok": True,
        "data": data,
        "slug": body.slug,
        "feito": body.feito,
        "template": template,
    }


# --- Shutdown (A2, 19h): encerrar o TRABALHO ---------------------------------
# Dois ritos diferentes (decisão do Leo): o Shutdown das 19h fecha o trabalho e planeja
# amanhã; o fechamento das 21h (abaixo) é o diário + as rotinas. As prioridades salvas
# aqui são o que o GET /abertura de amanhã mostra em `prioridades_de_ontem`.


@app.get("/shutdown")
async def get_shutdown(
    dia: str | None = Query(default=None, alias="data"),
    _=Depends(require_auth),
):
    ref = _data_ref(dia)
    pack = await tasks.shutdown_pack()
    salvo = store.get_shutdown(ref.isoformat())
    return {
        "data": ref.isoformat(),
        **pack,
        "prioridades": salvo["prioridades"] if salvo else [],
        "feito": bool(salvo and salvo["feito_em"]),
    }


@app.post("/shutdown")
async def post_shutdown(body: ShutdownIn, _=Depends(require_auth)):
    """As (até 3) prioridades de AMANHÃ. Gravadas sob a data de HOJE — é o Shutdown de
    hoje que planeja amanhã, e é a abertura de amanhã que lê o Shutdown de ontem."""
    hoje = date.today().isoformat()
    salvo = store.save_shutdown(hoje, body.prioridades)
    store.log_event("shutdown", ref=hoje, meta={"n": len(body.prioridades)})
    return {"ok": True, "data": hoje, "prioridades": salvo["prioridades"], "feito": True}


class AprendizadoIn(BaseModel):
    """Entrada manual; espaços isolados não constituem aprendizado."""

    model_config = {"extra": "forbid"}

    texto: str
    sensivel: bool = False

    @field_validator("texto")
    @classmethod
    def validar_texto(cls, value: str) -> str:
        texto = value.strip()
        if not texto:
            raise ValueError("texto não pode ser vazio")
        return texto


class AprendizadoStatusIn(BaseModel):
    """Transições manuais; prática exige o endpoint que registra a semana."""

    model_config = {"extra": "forbid"}

    status: str

    @field_validator("status")
    @classmethod
    def validar_status(cls, value: str) -> str:
        if value not in {"novo", "aplicado", "arquivado"}:
            raise ValueError("status inválido")
        return value


@app.post("/anki/sugerir")
async def sugerir_anki(
    body: AnkiSugerirIn,
    _auth: None = Depends(require_auth),
) -> dict:
    """Propõe candidatos sem aprová-los automaticamente (lei 3)."""
    if body.session_id is not None:
        if not store.session_exists(body.session_id):
            raise HTTPException(404, "session_nao_encontrada")
        state = store.claim_anki_suggestion(body.session_id)
        if state == "done":
            cards = store.list_anki_cards_for_session(body.session_id)
            return {"cards": cards, "n": len(cards)}
        if state == "processing":
            raise HTTPException(409, "anki_suggestion_em_andamento")
    try:
        candidatos = await hermes_client.suggest_anki(body.notas)
    except Exception:
        if body.session_id is not None:
            store.release_anki_suggestion(body.session_id)
        # A resposta não inclui notas nem saída do modelo, conforme a lei 7.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="anki_indisponivel",
        ) from None

    try:
        cards = (
            store.finish_anki_suggestion(body.session_id, candidatos)
            if body.session_id is not None
            else store.add_anki_cards(candidatos)
        )
    except ValueError as exc:
        if body.session_id is not None:
            store.release_anki_suggestion(body.session_id)
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None

    return {"cards": cards, "n": len(cards)}


@app.get("/anki/cards")
def listar_anki_cards(
    status_filtro: str | None = Query(default=None, alias="status"),
    _auth: None = Depends(require_auth),
) -> dict:
    """Lista candidatos para que o Leo revise, edite e decida."""
    try:
        cards = store.list_anki_cards(status_filtro)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None

    return {"cards": cards}


@app.patch("/anki/cards/{id}")
def editar_anki_card(
    id: int,
    body: AnkiCardPatchIn,
    _auth: None = Depends(require_auth),
) -> dict:
    """Registra a edição ou decisão explícita do Leo sobre um candidato."""
    campos = body.model_dump(exclude_unset=True)

    try:
        card = store.update_anki_card(id, **campos)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from None

    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="anki_card_nao_encontrado",
        )

    return card


@app.post("/anki/export")
def exportar_anki(
    _auth: None = Depends(require_auth),
) -> dict:
    """Exporta somente cards já aprovados pelo Leo e reserva cada um uma vez."""
    linhas = store.claim_anki_export()
    if not linhas:
        return {"n": 0, "path": None, "tsv": ""}

    ids = [int(card["id"]) for card in linhas]
    conteudo = anki.tsv(linhas)
    pasta = Path(settings.db_path).parent / "exports"
    nome = datetime.now().strftime("anki-%Y%m%d-%H%M%S-%f-") + uuid4().hex[:8] + ".tsv"
    arquivo = pasta / nome
    temporario = arquivo.with_suffix(".tmp")
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        with temporario.open("x", encoding="utf-8", newline="") as destino:
            destino.write(conteudo)
        temporario.replace(arquivo)
        store.finish_anki_export(ids, success=True)
    except Exception:
        store.finish_anki_export(ids, success=False)
        temporario.unlink(missing_ok=True)
        raise

    return {
        "n": len(linhas),
        "path": str(arquivo),
        "tsv": conteudo,
    }


@app.get("/triagem")
async def triagem(_auth: object = Depends(require_auth)):
    """Entrega o lote de revisão; nenhuma tarefa é movida neste endpoint (lei 3)."""
    return await tasks.triagem_pack()


@app.post("/triagem/aplicar")
async def triagem_aplicar(
    body: TriagemAplicarIn,
    _auth: object = Depends(require_auth),
):
    """Aplica somente os movimentos enviados explicitamente pelo Leo."""
    movimentos = [
        (movimento.task_id, movimento.area)
        for movimento in body.movimentos
    ]
    return {"resultados": await tasks.aplicar_triagem(movimentos)}


@app.get("/aprendizados")
async def listar_aprendizados(
    status: str | None = None,
    _: str = Depends(require_auth),
):
    if status is not None and status not in {
        "novo",
        "pratica",
        "aplicado",
        "arquivado",
    }:
        raise HTTPException(status_code=422, detail="status_invalido")
    return {"aprendizados": store.list_aprendizados(status=status)}


@app.post("/aprendizados")
async def criar_aprendizado(
    body: AprendizadoIn,
    _: str = Depends(require_auth),
):
    """Captura manual feita no app, sem criar uma tarefa no ClickUp."""
    return store.add_aprendizado(
        body.texto,
        sensivel=body.sensivel,
    )


@app.post("/aprendizados/{id}/praticar")
async def praticar_aprendizado(
    id: int,
    _: str = Depends(require_auth),
):
    aprendizado = store.definir_pratica(
        id,
        agenda.semana_iso(date.today()),
    )
    if aprendizado is None:
        raise HTTPException(status_code=404, detail="aprendizado_nao_encontrado")
    return aprendizado


@app.post("/aprendizados/{id}/status")
async def alterar_status_aprendizado(
    id: int,
    body: AprendizadoStatusIn,
    _: str = Depends(require_auth),
):
    aprendizado = store.set_status_aprendizado(id, body.status)
    if aprendizado is None:
        raise HTTPException(status_code=404, detail="aprendizado_nao_encontrado")
    return aprendizado


@app.get("/objetivos")
async def get_objetivos(_=Depends(require_auth)):
    return {"objetivos": await objetivos.listar(date.today())}


@app.post("/objetivos")
async def post_objetivo(
    body: ObjetivoCreateIn,
    _=Depends(require_auth),
):
    if body.rotina_slug is not None:
        slugs = {
            rotina["slug"]
            for rotina in store.list_routines()
        }
        if body.rotina_slug not in slugs:
            raise HTTPException(422, "rotina_slug inexistente")

    criado = store.create_objetivo(
        body.nome,
        rotina_slug=body.rotina_slug,
        alvo_semana=body.alvo_semana,
    )
    return {"objetivo": criado}


@app.patch("/objetivos/{objetivo_id}")
async def patch_objetivo(
    objetivo_id: int,
    body: ObjetivoPatchIn,
    _=Depends(require_auth),
):
    campos = {}
    if "nome" in body.model_fields_set:
        campos["nome"] = body.nome
    if "alvo_semana" in body.model_fields_set:
        campos["alvo_semana"] = body.alvo_semana

    atualizado = store.update_objetivo(objetivo_id, **campos)
    if atualizado is None:
        raise HTTPException(404, "objetivo não encontrado")
    return {"objetivo": atualizado}


@app.delete("/objetivos/{objetivo_id}")
async def delete_objetivo(
    objetivo_id: int,
    _=Depends(require_auth),
):
    if not store.delete_objetivo(objetivo_id):
        raise HTTPException(404, "objetivo não encontrado")
    return {"ok": True}


def _objetivo_manual_ativo(objetivo_id: int) -> dict:
    """Valida existência e fonte antes de qualquer alteração de marca."""
    objetivo = store.get_objetivo(objetivo_id)
    if not objetivo or not objetivo["ativo"]:
        raise HTTPException(404, "objetivo não encontrado")
    if objetivo.get("rotina_slug"):
        raise HTTPException(
            422,
            "objetivo ligado a rotina deriva exclusivamente dos checks",
        )
    return objetivo


@app.post("/objetivos/{objetivo_id}/marcar")
async def marcar_objetivo(
    objetivo_id: int,
    body: ObjetivoMarcaIn,
    _=Depends(require_auth),
):
    _objetivo_manual_ativo(objetivo_id)
    marcada_em = _data_ref(body.data).isoformat()
    inseriu = store.marcar_objetivo(objetivo_id, marcada_em)
    return {"ok": True, "ja_estava": not inseriu}


@app.post("/objetivos/{objetivo_id}/desmarcar")
async def desmarcar_objetivo(
    objetivo_id: int,
    body: ObjetivoMarcaIn,
    _=Depends(require_auth),
):
    _objetivo_manual_ativo(objetivo_id)
    marcada_em = _data_ref(body.data).isoformat()
    removeu = store.desmarcar_objetivo(objetivo_id, marcada_em)
    return {"ok": True, "estava_marcado": removeu}


@app.get("/agenda")
async def get_agenda(
    dia: str | None = Query(default=None, alias="data"),
    _=Depends(require_auth),
):
    """Entrega a agenda e explicita o estado de cada fonte externa."""
    ref = _data_ref(dia)
    resposta = await agenda.do_dia(ref)
    resposta["tarefas_due"] = (
        await tasks.due_hoje() if ref == date.today() else []
    )
    return resposta


@app.post("/agenda/google-calendar")
async def criar_evento_google(
    body: GoogleCalendarEventIn,
    _=Depends(require_auth),
):
    """Escreve só no calendário pessoal após confirmação explícita no app."""
    try:
        evento = await google_calendar.create_event(
            body.titulo,
            body.data,
            body.hora,
            body.duracao_min,
            body.client_key,
        )
    except google_calendar.GoogleCalendarNotConfigured:
        raise HTTPException(503, "google_calendar_nao_configurado") from None
    except google_calendar.GoogleCalendarUnavailable:
        raise HTTPException(503, "google_calendar_indisponivel") from None
    except google_calendar.GoogleCalendarIdempotencyConflict:
        raise HTTPException(409, "client_key_payload_conflitante") from None
    return {"evento": evento}


@app.get("/temas")
async def get_temas(
    semana: str | None = Query(default=None),
    _=Depends(require_auth),
):
    chave = _semana_tema(semana)
    return {"semana": chave, "temas": store.list_temas(chave)}


@app.post("/temas")
async def post_tema(body: TemaIn, _=Depends(require_auth)):
    semana = body.semana or agenda.semana_iso(date.today())
    return store.add_tema(semana, body.texto)


@app.delete("/temas/{tema_id}")
async def remove_tema(tema_id: int, _=Depends(require_auth)):
    if not store.delete_tema(tema_id):
        raise HTTPException(404, "tema não encontrado")
    return {"ok": True}


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
            if tasks.is_primeiro_domingo(date.today()):
                text = text + "\n\n" + tasks.monthly_review_text()
        except Exception:
            # O nudge-base ainda é entregue se algum agregado estiver indisponível.
            pass
    entrega = await notify.notificar(f"nudge_{body.kind}", text)
    return {"ok": True, **entrega}


@app.post("/internal/notify")
async def internal_notify(
    body: NotifyIn,
    x_internal_token: str = Header(default=""),
):
    _check_internal(x_internal_token)
    # `title` legado é aceito no contrato, mas o canal único usa título neutro fixo.
    return await notify.notificar(
        body.kind,
        body.body,
        sensivel=body.sensivel,
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
    entrega = {"push": False, "telegram": False}
    if has_content:
        # `body_telegram` já vem neutralizado POR LINHA (áreas sensíveis) — é o corpo
        # de preview, e serve aos dois canais. O app lê o body_app inteiro no /digest.
        entrega = await notify.notificar("digest", result["body_telegram"])
    store.save_digest_run(
        today,
        result["body_app"],
        len(result["tasks"]),
        entrega["push"] or entrega["telegram"],
    )
    return {"count": len(result["tasks"]), "telegram": entrega["telegram"]}
