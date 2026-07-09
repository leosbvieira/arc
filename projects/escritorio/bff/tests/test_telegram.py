import httpx
from app import telegram
from app.config import settings


async def test_send_ok(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "T")
    monkeypatch.setattr(settings, "telegram_chat_id", "123")
    sent = {}
    def handler(req):
        sent["url"] = str(req.url)
        return httpx.Response(200, json={"ok": True})
    monkeypatch.setattr(telegram, "_transport", httpx.MockTransport(handler))
    assert await telegram.send("digest do dia") is True
    assert "botT/sendMessage" in sent["url"]


async def test_sem_token_e_noop(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    assert await telegram.send("x") is False
