"""A fonte única dos ritos. Antes disto, os horários viviam em cinco lugares."""
import json

import pytest

from app import ritos


def test_carrega_os_sete_ritos():
    assert [r["slug"] for r in ritos.RITOS] == [
        "toque", "checkin", "jornal", "digest", "shutdown", "closing", "review",
    ]


def test_hora_e_hora_curta():
    assert ritos.hora("shutdown") == "19:00"
    assert ritos.hora_curta("shutdown") == "19h"
    assert ritos.hora_curta("toque") == "5h30"
    assert ritos.hora_curta("checkin") == "8h20"


def test_slug_desconhecido_levanta():
    with pytest.raises(KeyError):
        ritos.hora("nao-existe")


def test_slugs_por_script():
    assert ritos.slugs_por_script("digest") == ["digest"]
    assert "closing" in ritos.slugs_por_script("nudge")
    assert "digest" not in ritos.slugs_por_script("nudge")


@pytest.mark.parametrize("quebra", [
    [{"slug": "a", "hora": "05:30", "dia": None, "task": "T A", "script": "nudge"},
     {"slug": "a", "hora": "06:30", "dia": None, "task": "T B", "script": "nudge"}],   # slug duplicado
    [{"slug": "a", "hora": "05:30", "dia": None, "task": "T", "script": "nudge"},
     {"slug": "b", "hora": "06:30", "dia": None, "task": "T", "script": "nudge"}],     # task duplicada
    [{"slug": "a", "hora": "5:30",  "dia": None, "task": "T", "script": "nudge"}],     # hora sem zero
    [{"slug": "a", "hora": "25:00", "dia": None, "task": "T", "script": "nudge"}],     # hora inválida
    [{"slug": "a", "hora": "05:30", "dia": "lunes", "task": "T", "script": "nudge"}],  # dia inválido
    [{"slug": "a", "hora": "05:30", "dia": None, "task": "T", "script": "cron"}],      # script inválido
    [{"slug": "a", "hora": "02:59", "dia": "domingo", "task": "T", "script": "nudge"}],  # semanal < 03:00
])
def test_validacao_rejeita(quebra):
    with pytest.raises(ValueError):
        ritos.validar(quebra)


def test_semanal_a_partir_das_tres_e_aceito():
    ritos.validar([{"slug": "a", "hora": "03:00", "dia": "domingo", "task": "T", "script": "nudge"}])
