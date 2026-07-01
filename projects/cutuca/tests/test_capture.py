from datetime import date

from fakes import FakeClickUp

from cutuca.capture import handle_message
from cutuca.config import Config
from cutuca.parser import ParseError

TODAY = date(2026, 6, 30)


def cfg() -> Config:
    c = Config()
    c.clickup.list_id = "LIST1"
    return c


def make_parse(result=None, raiser=None):
    def _parse(text, **kwargs):
        if raiser is not None:
            raise raiser
        return result
    return _parse


def test_complete_message_creates_and_confirms():
    clickup = FakeClickUp(assignee_ids=[42])
    parsed = {"assignee": "João", "titulo": "enviar relatório", "prazo_iso": "2026-07-03", "lista": None}
    reply = handle_message("...", clickup=clickup, config=cfg(), parse=make_parse(parsed), now=TODAY)

    assert reply.kind == "created"
    assert reply.text.startswith("✅ criei:")
    assert "João" in reply.text and "enviar relatório" in reply.text
    assert "03/07/2026" in reply.text
    assert clickup.created and clickup.created[0]["assignee_ids"] == [42]
    assert clickup.created[0]["due_date_ms"] is not None


def test_unparseable_asks_back():
    clickup = FakeClickUp()
    reply = handle_message("???", clickup=clickup, config=cfg(), parse=make_parse(None), now=TODAY)
    assert reply.kind == "askback"
    assert clickup.created == []  # nothing created


def test_missing_assignee_asks_back():
    parsed = {"assignee": None, "titulo": "x", "prazo_iso": "2026-07-03", "lista": None}
    clickup = FakeClickUp()
    reply = handle_message("x", clickup=clickup, config=cfg(), parse=make_parse(parsed), now=TODAY)
    assert reply.kind == "askback"
    assert "pra quem" in reply.text.lower()
    assert clickup.created == []  # nothing created


def test_missing_prazo_asks_back():
    parsed = {"assignee": "Ana", "titulo": "x", "prazo_iso": None, "lista": None}
    reply = handle_message("x", clickup=FakeClickUp(), config=cfg(), parse=make_parse(parsed), now=TODAY)
    assert reply.kind == "askback"
    assert "prazo" in reply.text.lower()


def test_parse_error_returns_error_reply():
    reply = handle_message("x", clickup=FakeClickUp(), config=cfg(),
                           parse=make_parse(raiser=ParseError("boom")), now=TODAY)
    assert reply.kind == "error"


def test_clickup_failure_returns_error_reply():
    parsed = {"assignee": "Ana", "titulo": "x", "prazo_iso": "2026-07-03", "lista": None}
    clickup = FakeClickUp(raise_on_create=True)
    reply = handle_message("x", clickup=clickup, config=cfg(), parse=make_parse(parsed), now=TODAY)
    assert reply.kind == "error"
