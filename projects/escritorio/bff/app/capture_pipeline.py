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
        name=nome,
        area=area,
        due_ts=due_ts,
        tags=tags,
        description=description,
    )


def _parse_quando(q: str | None) -> float | None:
    if not q:
        return None
    try:
        return datetime.strptime(q, "%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp()
    except (ValueError, TypeError):
        # Formato inválido ou não-string degrada para captura sem due. Não retenta:
        # o Raw já foi preservado e o restante do verdict continua utilizável.
        return None


async def _process_one(row: dict) -> None:
    cid = row["id"]
    raw_path = row["raw_path"]

    # Etapa 1: Raw, idempotente por coluna + path determinístico.
    if not raw_path:
        raw_path = await vault_client.write_raw(row["text"], cid, ts=row["ts"])
        store.mark_capture(cid, raw_path=raw_path)

    # Classifica em todo retry ainda não concluído. Isso recompõe due/tipo mesmo se
    # uma tentativa anterior já tiver criado ou reconciliado a tarefa no ClickUp.
    raw_verdict = await hermes_client.classify(row["text"])
    verdict = raw_verdict if isinstance(raw_verdict, dict) else {}

    raw_tipo = verdict.get("tipo")
    tipo = (
        raw_tipo
        if isinstance(raw_tipo, str) and raw_tipo in VALID_TIPOS
        else "nota"
    )

    raw_titulo = verdict.get("titulo")
    titulo = (
        raw_titulo.strip()
        if isinstance(raw_titulo, str) and raw_titulo.strip()
        else row["text"][:80]
    )
    due_ts = _parse_quando(verdict.get("quando"))

    # Etapa 2: Staging. Antes de criar, reconcilia um possível create que chegou
    # ao ClickUp mas cujo id não foi persistido localmente antes de um crash.
    if tipo != "nota" and not row["clickup_task_id"]:
        marker = f"[cap:{cid}]"
        existing_task_id = await clickup_client.find_task_by_marker(
            clickup_client.AREA_LISTS[STAGING],
            marker,
        )
        if existing_task_id is not None:
            store.mark_capture(cid, clickup_task_id=existing_task_id)
        else:
            if tipo == "cobranca":
                titulo = (
                    f"Cobrar: {titulo}"
                    if not titulo.lower().startswith("cobrar")
                    else titulo
                )
            task = await _create_task(
                STAGING,
                titulo,
                due_ts=due_ts,
                tags=["aguardando"] if tipo == "cobranca" else None,
                description=f"{marker} raw: {raw_path}",
            )
            store.mark_capture(cid, clickup_task_id=task["id"])

    # Etapa 3: lembrete independente da criação da task. O marker no ref torna a
    # etapa retomável após crash e impede duplicação em retries posteriores.
    schedule_fragment = f"(c{cid})"
    if due_ts and not store.has_schedule_ref(schedule_fragment):
        store.add_schedule(
            due_ts,
            "cobrar-terceiro" if tipo == "cobranca" else "minha",
            f"item capturado com hora marcada {schedule_fragment} — abre o app",
        )

    store.mark_capture(cid, status="done")
    store.log_event("capture_done", ref=str(cid), meta={"tipo": tipo})


async def process_pending() -> int:
    done = 0
    for row in store.pending_captures():
        if not store.claim_capture(row["id"]):
            continue
        try:
            await _process_one(row)
            done += 1
        except Exception as e:  # noqa: BLE001 - a fila NUNCA derruba o worker
            if (
                isinstance(e, vault_client.VaultError)
                and str(e) == "vault_nao_configurado"
            ):
                store.mark_capture(
                    row["id"],
                    status="pending",
                    error=type(e).__name__,
                )
                logger.warning(
                    "vault sem configuração; worker aguardará antes de processar a fila"
                )
                break

            # Qualquer outra falha incrementa a tentativa e devolve o item para
            # pending; no teto ele vira failed, mas permanece persistido. Apenas a
            # classe sanitizada do erro vai para o banco/log (lei 7).
            store.mark_capture(
                row["id"],
                bump_attempts=True,
                error=type(e).__name__,
            )
            logger.warning(
                "captura %s falhou: %s (tentativa %s)",
                row["id"],
                type(e).__name__,
                row["attempts"] + 1,
            )
    return done
