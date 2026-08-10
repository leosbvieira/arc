"""Worker da fila: Raw verbatim -> classificacao -> Staging. Nada se perde; nada duplica; nada vaza.

Contrato B6/§10 (lei 3): toda tarefa cai em Staging — o destino final por area e do Leo,
na triagem. Cada etapa e idempotente por coluna da fila (raw_path, clickup_task_id) + path
deterministico do Raw, entao crash/retry em qualquer ponto nao reescreve nem duplica.
Higiene (lei 7): nenhum log/telemetria carrega o texto capturado nem stdout do Hermes.
"""
import logging
import re
from datetime import datetime

from . import clickup_client, hermes_client, store, tasks, vault_client, tz
from .clickup_client import STAGING

logger = logging.getLogger(__name__)
VALID_TIPOS = {"nota", "tarefa_pessoal", "tarefa_trabalho", "cobranca"}
TZ = tz.TZ

# Hooks textuais determinísticos (P2 item 10) — resolvidos ANTES do Hermes porque
# não exigem inferência. `sensivel:` marca a captura (lei 7); `hack:`/`aprendizado:`/
# `insight:` viram aprendizado (edificação) e nunca task; `melhoria:` vira item da
# fila de melhorias e também nunca task.
_SENSIVEL_PREFIX = re.compile(r"^\s*sens[ií]vel\s*:\s*", re.IGNORECASE)
_APRENDIZADO_PREFIX = re.compile(
    r"^\s*(?:hack|aprendizado|insight)\s*:\s*",
    re.IGNORECASE,
)
# O alvo é opcional e só aceita os três conhecidos. `melhoria xyz:` NÃO casa de
# propósito: cair na captura normal (Raw + triagem) é melhor que criar uma
# melhoria cujo texto começaria com "xyz:" — ruído que ninguém veria.
#
# `ideia:` NÃO entra aqui. A palavra já é da casa: é um dos modos da gramática de
# leitura (CAPTURE-GRAMMAR-SPEC.md) e a tela de Captura manda dizer "ideia" no
# ditado. Sequestrá-la fazia "ideia: levar a Maria pra jantar sexta" nunca chegar
# ao classificador — sem data, sem card, sem lembrete — com o recibo genérico
# "✅ anotado" escondendo a troca de destino.
_MELHORIA_PREFIX = re.compile(
    r"^\s*melhoria(?:\s+(app|empresa|fluxo))?\s*:\s*",
    re.IGNORECASE,
)


def _texto_sem_prefixo_sensivel(texto: str) -> tuple[str, bool]:
    """Remove somente o prefixo reconhecível; o Raw original permanece verbatim."""
    match = _SENSIVEL_PREFIX.match(texto)
    if match is None:
        return texto, False
    return texto[match.end():], True


def _texto_aprendizado(texto: str) -> str | None:
    """Reconhece aprendizado por prefixo, sem depender de classificação probabilística.

    Prefixo sozinho (ditado cortado, envio acidental) NÃO é aprendizado: cai no
    caminho normal em vez de virar um registro em branco que ninguém consegue ler
    nem descartar com sentido."""
    match = _APRENDIZADO_PREFIX.match(texto)
    if match is None:
        return None
    return texto[match.end():].strip() or None


def _texto_melhoria(texto: str) -> tuple[str, str | None] | None:
    """Reconhece melhoria por prefixo e devolve (texto, alvo); alvo é opcional.

    Declarar o alvo na captura é atrito, então sem ele o item entra a triar e a
    fila pergunta depois — um toque.

    Prefixo sem texto cai no caminho normal, mesma política de `melhoria xyz:`. A
    borda HTTP já recusava texto em branco com 422; a fila — que é justamente
    quem recebe entrada não controlada (voz, Telegram) — entrava sem guarda e
    produzia um card vazio impossível de triar, engrossando o "escolher 1" do
    review."""
    match = _MELHORIA_PREFIX.match(texto)
    if match is None:
        return None
    corpo = texto[match.end():].strip()
    if not corpo:
        return None
    alvo = match.group(1)
    return corpo, alvo.lower() if alvo else None


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

    # Hook `sensivel:` — o texto de PROCESSAMENTO perde o prefixo; o Raw não.
    texto_processamento, marcado_no_texto = _texto_sem_prefixo_sensivel(row["text"])
    sensivel = bool(row.get("sensivel")) or marcado_no_texto
    if marcado_no_texto and not bool(row.get("sensivel")):
        # A marca fica na fila para que retries posteriores continuem fail-closed.
        store.mark_capture(cid, sensivel=True)

    # Etapa 1: Raw, idempotente por coluna + path determinístico (verbatim, com prefixos).
    if not raw_path:
        raw_path = await vault_client.write_raw(row["text"], cid, ts=row["ts"])
        store.mark_capture(cid, raw_path=raw_path)

    # Hook de aprendizado (edificação): não é tarefa, não paga classificação de modelo.
    # O UNIQUE de origem_captura_id torna o hook retomável sem duplicar.
    aprendizado = _texto_aprendizado(texto_processamento)
    if aprendizado is not None:
        store.add_aprendizado(
            aprendizado,
            sensivel=sensivel,
            origem_captura_id=cid,
        )
        store.mark_capture(cid, status="done")
        store.log_event("capture_done", ref=str(cid), meta={"tipo": "aprendizado"})
        return

    # Hook de melhoria: fila própria, sem prazo e sem ClickUp. Uma melhoria em
    # lista de tarefas ou não tem prazo (morre no backlog) ou ganha um prazo
    # inventado (vira atraso). O UNIQUE de origem_captura_id retoma sem duplicar.
    melhoria = _texto_melhoria(texto_processamento)
    if melhoria is not None:
        texto_melhoria, alvo = melhoria
        store.add_melhoria(
            texto_melhoria,
            alvo=alvo,
            sensivel=sensivel,
            origem_captura_id=cid,
        )
        store.mark_capture(cid, status="done")
        store.log_event("capture_done", ref=str(cid), meta={"tipo": "melhoria"})
        return

    # Classifica em todo retry ainda não concluído. Isso recompõe due/tipo mesmo se
    # uma tentativa anterior já tiver criado ou reconciliado a tarefa no ClickUp.
    raw_verdict = await hermes_client.classify(
        texto_processamento,
        areas=tasks.AREAS_TRIAGEM,
    )
    verdict = raw_verdict if isinstance(raw_verdict, dict) else {}

    # A área proposta é guardada AQUI, no fundo, e a triagem só lê. Validamos
    # contra a lista antes de gravar: proposta fora do vocabulário é lixo, e lixo
    # gravado vira sugestão errada na tela do Leo depois. Vale null.
    raw_area = verdict.get("area")
    if isinstance(raw_area, str) and raw_area in tasks.AREAS_TRIAGEM:
        store.mark_capture(cid, area_proposta=raw_area)

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
        else texto_processamento[:80]
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
            # A tag `sensivel` viaja com a task: é ela que o digest/ritos usam pra
            # neutralizar o preview (lei 7) mesmo em área não-sensível.
            tags: list[str] = []
            if tipo == "cobranca":
                tags.append("aguardando")
            if sensivel:
                tags.append("sensivel")
            task = await _create_task(
                STAGING,
                titulo,
                due_ts=due_ts,
                tags=tags or None,
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
