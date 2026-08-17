"""A rajada de boot: seis ritos entregues no mesmo segundo, e o de 5h30 às 22h44.

`notif_log` registrou essa rajada em SETE dias diferentes. A causa tinha duas metades
e as duas estão testadas aqui: o `-StartWhenAvailable` do Agendador (que manda o
Windows executar todo gatilho perdido no boot) e a ausência de qualquer noção de
"tarde demais" no servidor.
"""
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import ritos, store, tz
from app.config import settings
from app.main import app
from app.tz import TZ

_SYNC_CRON = Path(__file__).resolve().parent.parent / "scripts" / "sync-cron.ps1"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(settings, "internal_token", "itok")
    store.init_db()
    return TestClient(app)


def em(dia_hora: str) -> datetime:
    """'2026-08-15 22:44' -> datetime no fuso do Leo."""
    return datetime.strptime(dia_hora, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)


# 2026-08-15 é um sábado; 2026-08-16, um domingo.


def test_o_toque_das_5h30_nao_sai_as_22h44():
    assert ritos.atrasado("toque", em("2026-08-15 22:44"))


def test_o_rito_na_hora_sai():
    assert not ritos.atrasado("toque", em("2026-08-15 05:30"))


def test_atraso_curto_ainda_sai_porque_o_bff_pode_estar_subindo():
    # `nudge.ps1` fica repetindo /health até o BFF responder: um atraso de minutos
    # é o funcionamento normal, não a falha que se quer barrar.
    assert not ritos.atrasado("toque", em("2026-08-15 06:15"))


def test_a_borda_da_tolerancia_e_inclusiva():
    assert not ritos.atrasado("toque", em("2026-08-15 07:00"))   # +90
    assert ritos.atrasado("toque", em("2026-08-15 07:01"))       # +91


def test_antes_da_hora_nunca_e_atraso():
    assert ritos.atraso_minutos("closing", em("2026-08-15 20:00")) == -60
    assert not ritos.atrasado("closing", em("2026-08-15 20:00"))


def test_o_review_de_domingo_nao_sai_na_segunda_no_mesmo_horario():
    # Sem o recorte por dia da semana este seria o furo mais fácil: a comparação
    # só de horário aprovaria 20h05 de qualquer dia.
    assert not ritos.atrasado("review", em("2026-08-16 20:05"))  # domingo, ok
    assert ritos.atrasado("review", em("2026-08-17 20:05"))      # segunda, não


def test_atraso_minutos_devolve_none_fora_do_dia_do_rito():
    assert ritos.atraso_minutos("review", em("2026-08-17 20:05")) is None
    assert ritos.atraso_minutos("review", em("2026-08-16 20:05")) == 5


def test_todos_os_ritos_de_nudge_sao_barrados_na_rajada_das_22h44():
    # O caso real de 15/ago, rito por rito — é o teste que descreve o bug.
    rajada = em("2026-08-15 22:44")
    for slug in ritos.slugs_por_script("nudge"):
        if slug == "closing":
            continue  # 21h: dentro da tolerância às 22h44, e legitimamente
        assert ritos.atrasado(slug, rajada), f"{slug} passaria na rajada"


def test_o_endpoint_recusa_o_atrasado_e_nao_queima_o_slot_do_dia(client, monkeypatch):
    """A metade que importa: recusar sem MARCAR como enviado.

    Se o atrasado consumisse o dedupe do dia, a guarda trocaria um problema por
    outro — o toque das 22h44 sumiria, e o das 5h30 do dia seguinte também.
    """
    monkeypatch.setattr(tz, "agora_local", lambda: em("2026-08-15 22:44"))
    r = client.post(
        "/internal/nudge", json={"kind": "toque"}, headers={"X-Internal-Token": "itok"}
    )
    assert r.status_code == 200
    assert r.json() == {"skipped": "atrasado"}
    assert not store.notif_sent_today("nudge_toque")


def test_o_endpoint_entrega_o_rito_na_hora(client, monkeypatch):
    # O contrapeso do teste acima: a guarda não pode barrar o caminho feliz.
    monkeypatch.setattr(tz, "agora_local", lambda: em("2026-08-15 05:31"))

    async def entregue(_chave, _texto, **_kw):
        return {"telegram": True}

    monkeypatch.setattr("app.main.notify.notificar", entregue)
    r = client.post(
        "/internal/nudge", json={"kind": "toque"}, headers={"X-Internal-Token": "itok"}
    )
    assert r.status_code == 200 and r.json()["ok"] is True


def test_o_agendador_nao_registra_mais_os_ritos_com_start_when_available():
    # O `-DryRun` do sync-cron.ps1 não chega a montar as settings, então a garantia
    # é sobre o texto — mesmo padrão que test_ritos.py usa com o nudge.ps1.
    texto = _SYNC_CRON.read_text(encoding="utf-8")
    ativas = [
        linha for linha in texto.splitlines()
        if "-StartWhenAvailable" in linha and not linha.lstrip().startswith("#")
    ]
    assert ativas == [], f"voltou a agendar com catch-up: {ativas}"
