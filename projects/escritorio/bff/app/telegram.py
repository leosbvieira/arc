"""Canal Telegram do P1. Texto plano; conteúdo já chega neutralizado pelo chamador."""
import logging

import httpx

from .config import settings

logger = logging.getLogger(__name__)
_transport: httpx.AsyncBaseTransport | None = None


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
    except Exception as e:  # noqa: BLE001 - canal nunca propaga falha ao chamador
        logger.warning("telegram falhou: %s", type(e).__name__)
        return False
