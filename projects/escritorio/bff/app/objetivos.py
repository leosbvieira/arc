"""Objetivos acumulativos derivados de marcações manuais ou checks de rotina.

Cada objetivo tem uma única fonte de verdade durante toda a sua vida:

- objetivo ligado a rotina deriva exclusivamente de ``routine_checks``;
- objetivo sem rotina usa ``objetivo_marcas``.

A separação evita misturar históricos incompatíveis e mantém o dashboard factual.
"""

from datetime import date, timedelta

from . import pontos, store

_INICIO_DOS_TEMPOS = "0001-01-01"


def _data_iso(valor: str) -> date | None:
    """Converte uma data persistida; linha inválida não entra no agregado."""
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def _chave_semana(segunda: date) -> str:
    iso = segunda.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def progresso(
    objetivo: dict,
    checks: list[dict],
    marcas: list[str],
    ref: date,
) -> dict:
    """Calcula total, semana atual e série das últimas 12 semanas ISO.

    O alvo é apenas uma referência aritmética de aderência. O percentual pode passar
    de 100 quando houver mais marcações que o alvo; isso descreve o dado sem julgamento.
    """
    rotina_slug = objetivo.get("rotina_slug")

    if rotina_slug:
        valores = {
            row["data"]
            for row in checks
            if row.get("rotina") == rotina_slug and bool(row.get("feito"))
        }
    else:
        valores = set(marcas)

    datas = {
        data_convertida
        for valor in valores
        if (data_convertida := _data_iso(valor)) is not None
    }

    semana_atual = pontos.segunda_da_semana(ref)
    primeira_semana = semana_atual - timedelta(weeks=11)
    por_semana = {
        primeira_semana + timedelta(weeks=indice): 0
        for indice in range(12)
    }

    for marcada_em in datas:
        segunda = pontos.segunda_da_semana(marcada_em)
        if segunda in por_semana:
            por_semana[segunda] += 1

    n_atual = por_semana[semana_atual]
    alvo = objetivo.get("alvo_semana")
    pct = round(100 * n_atual / alvo) if alvo else None

    return {
        "total": len(datas),
        "semana_atual": {
            "n": n_atual,
            "alvo": alvo,
            "pct": pct,
        },
        "serie": [
            {
                "semana": _chave_semana(segunda),
                "n": por_semana[segunda],
            }
            for segunda in sorted(por_semana)
        ],
    }


async def listar(ref: date) -> list[dict]:
    """Lista objetivos ativos com uma única leitura compartilhada dos checks."""
    itens = store.list_objetivos()
    checks = store.get_checks_since(_INICIO_DOS_TEMPOS)

    resposta = []
    for objetivo in itens:
        marcas = (
            []
            if objetivo.get("rotina_slug")
            else store.marcas_do_objetivo(objetivo["id"])
        )
        resposta.append({
            **objetivo,
            "progresso": progresso(objetivo, checks, marcas, ref),
        })
    return resposta
