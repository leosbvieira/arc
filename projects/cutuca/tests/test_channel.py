import pytest
from fakes import FakeResponse, FakeSession

from cutuca.telegram_channel import TelegramChannel


def test_send_posts_to_bot_api():
    captured = {}

    def handler(method, url, kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return FakeResponse({"ok": True, "result": {"message_id": 1}})

    ch = TelegramChannel("TOKEN123", session=FakeSession(handler))
    out = ch.send(999, "olá")

    assert "/botTOKEN123/sendMessage" in captured["url"]
    assert captured["json"] == {"chat_id": 999, "text": "olá"}
    assert out["ok"] is True


def test_send_raises_on_http_error():
    def handler(method, url, kwargs):
        return FakeResponse(status_code=400, text="bad request")

    ch = TelegramChannel("TOKEN123", session=FakeSession(handler))
    with pytest.raises(RuntimeError):
        ch.send(1, "x")
