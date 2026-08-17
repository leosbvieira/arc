"""A fonte única dos ritos. Antes disto, os horários viviam em cinco lugares."""
import json
import re

import pytest

from app import main, ritos

_HORA_NO_TEXTO = re.compile(r"\b\d{1,2}h(\d{2})?\b")


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


def test_template_do_nudge_nao_tem_hora_escrita_a_mao():
    for slug, texto in main.NUDGE_TEMPLATE.items():
        assert not _HORA_NO_TEXTO.search(texto), f"{slug} tem hora no template: {texto!r}"


def test_cada_nudge_mostra_a_hora_do_proprio_slug():
    """Sentinela distinta por slug: pega o copy que interpola a hora do rito errado."""
    sentinelas = {r["slug"]: f"{i + 1}h{i + 1:02d}" for i, r in enumerate(ritos.RITOS)}
    copy = main.montar_nudge_copy(lambda slug: sentinelas[slug])
    for slug, texto in copy.items():
        assert sentinelas[slug] in texto, f"{slug} não mostra a própria hora: {texto!r}"
        for outro, s in sentinelas.items():
            if outro != slug:
                assert s not in texto, f"{slug} mostra a hora de {outro}"


def test_chaves_do_nudge_copy_sao_exatamente_os_slugs_nudge():
    assert set(main.NUDGE_COPY) == set(ritos.slugs_por_script("nudge"))


def test_validateset_do_nudge_ps1_bate_com_os_slugs():
    """O ValidateSet é a primeira linha do script: slug fora dele mata o rito
    antes de qualquer chamada HTTP."""
    from pathlib import Path
    fonte = (Path(__file__).resolve().parent.parent / "scripts" / "nudge.ps1").read_text(encoding="utf-8")
    membros = set(re.findall(r'"([a-z]+)"', fonte.splitlines()[0]))
    assert membros == set(ritos.slugs_por_script("nudge"))
