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


def _push_entregou(resultado: dict) -> bool:
    """Entrega real: o Expo aceitou pelo menos uma mensagem e não devolveu ticket de erro
    (DeviceNotRegistered, token inválido...). Fail-closed: na dúvida, a ponte sobe."""
    if int(resultado.get("sent") or 0) <= 0:
        return False
    tickets = resultado.get("tickets") or []
    return not any(
        isinstance(t, dict) and t.get("status") == "error" for t in tickets
    )


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
        return _push_entregou(
            await push.send_push(tokens, TITULO, corpo, {"kind": kind})
        )
    except Exception as e:  # noqa: BLE001 - canal nunca propaga falha ao chamador
        logger.warning("push falhou: %s", type(e).__name__)
        return False


async def _tentar_telegram(corpo: str) -> bool:
    try:
        return bool(await telegram.send(corpo))
    except Exception as e:  # noqa: BLE001 - canal nunca propaga falha ao chamador
        logger.warning("telegram falhou: %s", type(e).__name__)
        return False


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
