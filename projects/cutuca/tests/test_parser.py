from datetime import date

import pytest
from fakes import FakeAnthropic

from cutuca.parser import ParseError, missing_fields, parse_task

TODAY = date(2026, 6, 30)


def test_valid_json():
    client = FakeAnthropic(
        '{"assignee": "João", "titulo": "enviar relatório", '
        '"prazo_iso": "2026-07-03", "lista": "financeiro"}'
    )
    got = parse_task("joão manda o relatório sexta", client=client, today=TODAY)
    assert got == {
        "assignee": "João",
        "titulo": "enviar relatório",
        "prazo_iso": "2026-07-03",
        "lista": "financeiro",
    }


def test_strips_markdown_fences():
    client = FakeAnthropic('```json\n{"assignee":"Ana","titulo":"x","prazo_iso":null,"lista":null}\n```')
    got = parse_task("ana faz x", client=client, today=TODAY)
    assert got["assignee"] == "Ana"
    assert got["prazo_iso"] is None


def test_finds_object_inside_preamble():
    client = FakeAnthropic('Claro! Aqui: {"assignee":"Ana","titulo":"x","prazo_iso":null,"lista":null} ok')
    got = parse_task("ana faz x", client=client, today=TODAY)
    assert got["titulo"] == "x"


def test_malformed_returns_none():
    client = FakeAnthropic("desculpa, não consegui")
    assert parse_task("???", client=client, today=TODAY) is None


def test_missing_title_returns_none():
    client = FakeAnthropic('{"assignee":"Ana","titulo":"","prazo_iso":null,"lista":null}')
    assert parse_task("ana", client=client, today=TODAY) is None


def test_invalid_prazo_becomes_null():
    client = FakeAnthropic('{"assignee":"Ana","titulo":"x","prazo_iso":"sexta","lista":null}')
    got = parse_task("...", client=client, today=TODAY)
    assert got["prazo_iso"] is None


def test_blank_input_returns_none():
    assert parse_task("   ", client=FakeAnthropic("{}"), today=TODAY) is None


def test_client_failure_raises_parseerror():
    client = FakeAnthropic(raiser=RuntimeError("429 overloaded"))
    with pytest.raises(ParseError):
        parse_task("qualquer", client=client, today=TODAY)


def test_today_is_passed_to_model():
    client = FakeAnthropic('{"assignee":"Ana","titulo":"x","prazo_iso":null,"lista":null}')
    parse_task("ana faz x amanhã", client=client, today=TODAY)
    sent = client.messages.calls[0]["messages"][0]["content"]
    assert "2026-06-30" in sent


def test_missing_fields_helper():
    assert missing_fields(None) == ["assignee", "prazo_iso"]
    assert missing_fields({"assignee": "Ana", "titulo": "x", "prazo_iso": None, "lista": None}) == ["prazo_iso"]
    assert missing_fields({"assignee": "Ana", "titulo": "x", "prazo_iso": "2026-07-01", "lista": None}) == []
