"""The ONE channel seam (SPEC NFR-4 / FR-8). Sending is a plain HTTPS POST to the
Telegram Bot API, so Flow B (the digest) needs no telegram library at all and the
seam is trivially mockable. Swapping to WhatsApp later = a new class with .send().

The long-poll *listener* (Flow A input) lives in app.py and uses python-telegram-bot;
that library is only needed there, not for sending.
"""

from __future__ import annotations

from typing import Any, Optional

API_ROOT = "https://api.telegram.org"


class Channel:
    """Interface marker: anything with .send(chat_id, text) is a channel."""

    def send(self, chat_id: Any, text: str) -> dict:  # pragma: no cover - interface
        raise NotImplementedError


class TelegramChannel(Channel):
    def __init__(self, token: str, *, session: Any = None, timeout: float = 15):
        self.token = token
        self.timeout = timeout
        if session is not None:
            self.session = session
        else:
            import requests  # lazy

            self.session = requests.Session()

    def send(self, chat_id: Any, text: str, *, parse_mode: Optional[str] = None) -> dict:
        url = f"{API_ROOT}/bot{self.token}/sendMessage"
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        status = getattr(resp, "status_code", 200)
        if status >= 400:
            raise RuntimeError(f"telegram sendMessage -> {status}: {getattr(resp, 'text', '')}")
        return resp.json()
