"""O fuso do Leo, num lugar só.

`TZ = ZoneInfo("America/Sao_Paulo")` estava duplicado em 11 pontos do BFF, e o
comentário em `hermes_client.py` já pedia a extração "se virar um 3º uso". Pior:
`store.py` gravava `data_local` com `date.today()` — o relógio do PROCESSO — e não
podia importar `pontos.hoje_local()` porque `pontos` importa `store`.

Num VPS em UTC (o próximo passo declarado), das 21h à meia-noite BRT o servidor já
está em D+1. O rito das 21h gravaria o dedupe de notificação no dia seguinte: o
`notif_sent_today` não encontraria o envio, e o aviso sairia DUAS vezes.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app import store, tz
from app.config import settings


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()


def test_tz_e_o_fuso_do_leo():
    assert tz.TZ == ZoneInfo("America/Sao_Paulo")


def test_hoje_local_nao_e_o_relogio_do_processo(monkeypatch):
    """23h30 BRT em 04/ago é 02h30 UTC de 05/ago. A resposta certa é 04."""
    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tzinfo=None):
            momento = datetime(2026, 8, 5, 2, 30, tzinfo=ZoneInfo("UTC"))
            return momento.astimezone(tzinfo) if tzinfo else momento.replace(tzinfo=None)

    monkeypatch.setattr(tz, "datetime", FakeDatetime)
    assert tz.hoje_local() == date(2026, 8, 4)


def test_pontos_usa_a_mesma_fonte():
    """Uma definição só: se `pontos` mantiver a própria, elas divergem em silêncio."""
    from app import pontos

    assert pontos.hoje_local() == tz.hoje_local()


def test_notif_dedupe_usa_a_data_do_leo(monkeypatch):
    monkeypatch.setattr(store.tz, "hoje_local", lambda: date(2026, 8, 4))

    store.log_notif("nudge_closing", "push", True)

    with store._connect() as con:
        data = con.execute("SELECT data_local FROM notif_log").fetchone()[0]
    assert data == "2026-08-04"
    assert store.notif_sent_today("nudge_closing") is True
