"""A camada única de notificação (P2 item 4) — TUDO que avisa o Leo passa por aqui.

O buraco que isto fecha: `app/push.py` e `POST /internal/notify` existiam desde o P1 e
**ninguém chamava**. Cada lugar que avisava (digest, nudges, ⏰ da hora marcada) falava
com o `telegram.send` direto — então 100% dos avisos saíam por Telegram, embora o Leo
tenha pedido notificação pelo app três vezes.

As três regras deste módulo:

1. **Push primeiro.** É o canal que ele pediu, e é o único que abre no lugar certo do app.
2. **Telegram é a PONTE, não o canal.** A SPEC: *"Telegram = ponte de transição até o push
   in-app existir"*. Logo, ele só sobe quando o push NÃO entregou — sem device registrado,
   erro de rede, ou ticket de erro do Expo (device desinstalado). Enquanto não houver
   device, o comportamento é byte-a-byte o de hoje: tudo por Telegram.
3. **Lei 7 no preview.** O corpo do push aparece no lockscreen exatamente como o texto do
   Telegram. Item sensível vai NEUTRO nos dois — a regra mora em `tasks.neutralizar`, que
   é a mesma que o digest usa; aqui não se reimplementa nada disso.

Nunca propaga exceção: um canal fora do ar não pode derrubar o cron, o worker do
scheduler nem o request. O que sobrevive é o `notif_log` — que registra o canal REAL
usado, e é dele que sai o dedupe por dia (`notif_sent_today`).
"""
import logging

from . import push, store, tasks, telegram

logger = logging.getLogger(__name__)

TITULO = "Escritório"


def _avaliar_push(resultado: dict, tokens: list[str]) -> tuple[bool, list[str]]:
    """Retorna (alguma_entrega, tokens_stale), preservando ticket↔token por posição."""
    tickets = resultado.get("tickets")
    if not isinstance(tickets, list) or not tickets or len(tickets) != len(tokens):
        return False, []

    entregou = False
    stale: list[str] = []
    for token, ticket in zip(tokens, tickets, strict=True):
        if not isinstance(ticket, dict):
            continue
        if ticket.get("status") == "ok":
            entregou = True
            continue
        details = ticket.get("details")
        error = details.get("error") if isinstance(details, dict) else None
        if error == "DeviceNotRegistered" or ticket.get("message") == "DeviceNotRegistered":
            stale.append(token)
    return entregou, stale


def _tickets_com_token(resultado: dict, tokens: list[str]) -> list[tuple[str, str]]:
    """Pareia ticket↔token por posição, como o `_avaliar_push` — a Expo devolve os
    tickets na mesma ordem das mensagens enviadas."""
    tickets = resultado.get("tickets")
    if not isinstance(tickets, list) or len(tickets) != len(tokens):
        return []
    pares = []
    for token, ticket in zip(tokens, tickets, strict=True):
        if isinstance(ticket, dict) and isinstance(ticket.get("id"), str):
            pares.append((ticket["id"], token))
    return pares


async def _tentar_push(kind: str, corpo: str) -> bool:
    try:
        tokens = store.list_devices()
    except Exception:  # noqa: BLE001 - sem devices legíveis, a ponte assume
        logger.exception("notificar: leitura de devices falhou")
        return False
    if not tokens:
        return False
    try:
        # `data` carrega só o kind (pro app abrir na tela certa) — nunca conteúdo.
        resultado = await push.send_push(tokens, TITULO, corpo, {"kind": kind})
        entregou, stale = _avaliar_push(resultado, tokens)
        # O ticket só diz que a Expo ACEITOU. Guarda para conferir o recibo depois —
        # é lá que ela reporta DeviceNotRegistered, e sem isso o log mente.
        try:
            store.registrar_tickets(_tickets_com_token(resultado, tokens))
        except Exception:  # noqa: BLE001 — conferência é bônus, não trava o aviso
            logger.warning("notificar: registro de tickets falhou")
        if stale:
            try:
                store.remove_devices(stale)
            except Exception:  # limpeza não muda uma entrega já confirmada
                logger.exception("notificar: remoção de device stale falhou")
        return entregou
    except Exception as e:  # noqa: BLE001 - canal nunca propaga falha ao chamador
        logger.warning("push falhou: %s", type(e).__name__)
        return False


async def _tentar_telegram(corpo: str) -> bool:
    try:
        return bool(await telegram.send(corpo))
    except telegram.EntregaIncerta:
        # Pode ter chegado. Sobe até a rota, que marca a reserva do dia como
        # `incerto` em vez de liberar pra reenvio.
        raise
    except Exception as e:  # noqa: BLE001 - canal nunca propaga falha ao chamador
        logger.warning("telegram falhou: %s", type(e).__name__)
        return False


async def conferir_recibos(idade_minima_s: float = 900) -> None:
    """Segunda passada: pergunta à Expo se o push realmente chegou.

    Sem isto, um token morto devolvia ticket `ok`, o `_avaliar_push` concluía
    "entregou", a ponte do Telegram nunca subia e o `notif_log` registrava sucesso —
    o log mentindo justamente sobre a falha que a gente usaria o log para achar.

    Best-effort: Expo fora do ar não derruba nada e não descarta o ticket, que volta
    na próxima passada.
    """
    pendentes = store.tickets_a_conferir(idade_minima_s)
    if not pendentes:
        return

    por_ticket = {p["ticket_id"]: p["token"] for p in pendentes}
    try:
        recibos = await push.get_receipts(list(por_ticket))
    except Exception as e:  # noqa: BLE001 — lei 7: só a classe do erro
        logger.warning("recibos de push: %s", type(e).__name__)
        return

    mortos: list[str] = []
    resolvidos: list[str] = []
    for ticket_id, recibo in recibos.items():
        if not isinstance(recibo, dict):
            continue
        resolvidos.append(ticket_id)
        detalhes = recibo.get("details")
        erro = detalhes.get("error") if isinstance(detalhes, dict) else None
        if erro == "DeviceNotRegistered":
            token = por_ticket.get(ticket_id)
            if token:
                mortos.append(token)

    if mortos:
        store.remove_devices(mortos)
        store.log_event("push_device_expirado", meta={"n": len(mortos)})
    store.descartar_tickets(resolvidos)


async def notificar(kind: str, texto: str, *, sensivel: bool = False) -> dict:
    """Avisa o Leo por push; cai pro Telegram quando o push não entrega.

    `kind` é a chave do `notif_log` — e é ela que o dedupe por dia usa
    (`store.notif_sent_today(kind)`), então tem que ser estável ('digest',
    'nudge_closing', 'hora_marcada'...).
    """
    corpo = tasks.neutralizar(texto, sensivel=sensivel)

    push_ok = await _tentar_push(kind, corpo)
    telegram_ok = False if push_ok else await _tentar_telegram(corpo)

    # O canal REAL: 'push' quando ele entregou; senão o Telegram foi quem tentou —
    # entregando ou não (uma falha de entrega fica registrada como entregue=0, e é
    # isso que permite o retry no mesmo dia sem consumir o slot do dedupe).
    canal = "push" if push_ok else "telegram"
    try:
        store.log_notif(kind, canal, push_ok or telegram_ok)
    except Exception:  # noqa: BLE001 - um log ruim não derruba o aviso
        logger.exception("notificar: log de notificação falhou")

    return {"push": push_ok, "telegram": telegram_ok}
