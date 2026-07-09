"""Worker da fila: Raw verbatim -> classificacao -> Staging. Nada se perde; nada duplica; nada vaza.

Contrato B6/§10 (lei 3): toda tarefa cai em Staging — o destino final por area e do Leo,
na triagem. Cada etapa e idempotente por coluna da fila (raw_path, clickup_task_id) + path
deterministico do Raw, entao crash/retry em qualquer ponto nao reescreve nem duplica.
Higiene (lei 7): nenhum log/telemetria carrega o texto capturado nem stdout do Hermes.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from . import clickup_client, hermes_client, store, vault_client
from .clickup_client import STAGING

logger = logging.getLogger(__name__)
VALID_TIPOS = {"nota", "tarefa_pessoal", "tarefa_trabalho", "cobranca"}
TZ = ZoneInfo("America/Sao_Paulo")


async def _create_task(area, nome, due_ts=None, tags=None, description=None):
    """Wrapper que os testes fakeiam. Reconcilia a ordem real de clickup_client.create,
    que e create(name, area, ...) (Task 6) — aqui a assinatura fica (area, nome, ...) porque
    e como o plano/testes chamam; passo por keyword pra nao inverter os dois."""
    return await clickup_client.create(
        name=nome, area=area, due_ts=due_ts, tags=tags, description=description
    )


def _parse_quando(q: str | None) -> float | None:
    if not q:
        return None
    try:
        return datetime.strptime(q, "%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp()
    except ValueError:
        return None


async def _process_one(row: dict) -> None:
    cid = row["id"]
    raw_path = row["raw_path"]
    if not raw_path:                                   # etapa 1: Raw (idempotente por coluna + path deterministico)
        raw_path = await vault_client.write_raw(row["text"], cid, ts=row["ts"])
        store.mark_capture(cid, raw_path=raw_path)
    verdict = await hermes_client.classify(row["text"])
    tipo = verdict.get("tipo")
    if tipo not in VALID_TIPOS:
        tipo = "nota"                                  # degrada: Raw ja cumpriu a lei 1
    if tipo != "nota" and not row["clickup_task_id"]:  # etapa 2: Staging (idempotente por coluna)
        titulo = (verdict.get("titulo") or row["text"][:80]).strip()
        if tipo == "cobranca":
            titulo = f"Cobrar: {titulo}" if not titulo.lower().startswith("cobrar") else titulo
        due_ts = _parse_quando(verdict.get("quando"))
        task = await _create_task(
            STAGING, titulo, due_ts=due_ts,
            tags=["aguardando"] if tipo == "cobranca" else None,
            description=f"[cap:{cid}] raw: {raw_path}",
        )
        store.mark_capture(cid, clickup_task_id=task["id"])
        if due_ts:                                     # lembrete GENERICO (B6/§10; texto neutro, sem conteudo)
            store.add_schedule(due_ts, "cobrar-terceiro" if tipo == "cobranca" else "minha",
                               f"item capturado com hora marcada (c{cid}) — abre o app")
    store.mark_capture(cid, status="done")
    store.log_event("capture_done", ref=str(cid), meta={"tipo": tipo})


async def process_pending() -> int:
    done = 0
    for row in store.pending_captures():
        try:
            await _process_one(row)
            done += 1
        except Exception as e:  # noqa: BLE001 - a fila NUNCA derruba o worker
            # O except largo subsume VaultError E httpx.HTTPError (o vault_client nao embrulha
            # erros de transporte httpx — handoff da Task 8): qualquer falha marca a tentativa e
            # segue; o Raw ja gravado persiste e o item volta na proxima rodada (nada se perde).
            store.mark_capture(row["id"], bump_attempts=True, error=type(e).__name__)  # SEM conteudo (lei 7)
            logger.warning("captura %s falhou: %s (tentativa %s)",
                           row["id"], type(e).__name__, row["attempts"] + 1)
    return done
