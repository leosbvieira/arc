"""Canal Telegram do P1. Texto plano; conteúdo já chega neutralizado pelo chamador."""
import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)
_transport: httpx.AsyncBaseTransport | None = None


class EntregaIncerta(Exception):
    """O request SAIU e a resposta não veio (ReadTimeout, conexão caiu no meio).

    A mensagem pode ter chegado. Devolver False aqui fazia o chamador liberar a
    reserva do dia e reenviar — digest em dobro (revisão Codex, 12/09/2026). Falha
    ANTES de enviar (sem token, ConnectTimeout, DNS) continua sendo False."""


async def send(text: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info("telegram desligado (sem token/chat_id)")
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15, transport=_transport) as c:
            r = await c.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
            )
        return r.status_code == 200 and r.json().get("ok", False)
    except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as e:
        logger.warning("telegram: entrega incerta: %s", type(e).__name__)
        raise EntregaIncerta(type(e).__name__) from None
    except Exception as e:  # noqa: BLE001 - canal nunca propaga falha ao chamador
        logger.warning("telegram falhou: %s", type(e).__name__)
        return False
