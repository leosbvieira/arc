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


async def test_read_timeout_e_entrega_incerta(monkeypatch):
    import pytest
    monkeypatch.setattr(settings, "telegram_bot_token", "T")
    monkeypatch.setattr(settings, "telegram_chat_id", "123")
    def handler(req):
        raise httpx.ReadTimeout("sem resposta", request=req)
    monkeypatch.setattr(telegram, "_transport", httpx.MockTransport(handler))
    with pytest.raises(telegram.EntregaIncerta):
        await telegram.send("digest do dia")


async def test_falha_antes_de_enviar_continua_false(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "T")
    monkeypatch.setattr(settings, "telegram_chat_id", "123")
    def handler(req):
        raise httpx.ConnectError("dns", request=req)
    monkeypatch.setattr(telegram, "_transport", httpx.MockTransport(handler))
    assert await telegram.send("x") is False
