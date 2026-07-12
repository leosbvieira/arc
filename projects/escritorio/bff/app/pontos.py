"""Pontos + Conquistas N1-4 (P2 item 3) — a punição do sistema, e só ela.

A regra, como o Leo travou (doc conceitual, 6ª rodada):

    "punição = PONTOS sobre as Conquistas N1-4 — fazer ganha, furar desconta pouco;
     o scorecard <85% + o Mentor são a dor principal. Linguagem jamais envergonha."

Três invariantes que este módulo protege:

1. **Pontos são DERIVADOS, não um saldo mutável.** Não existe tabela de ledger: tudo
   aqui é função pura de `routine_checks` + config. Recalcular o passado sempre dá o
   mesmo número, e o placar não pode desviar de si mesmo.

2. **Desconto SÓ em padrão, e pouco.** Furo isolado (1 ou 2) custa ZERO. Uma rotina em
   padrão custa `desconto_padrao` UMA vez na semana — por mais furos que ela tenha — e
   o total da semana ainda passa por `teto_desconto_semanal`.

3. **O nível é VITALÍCIO.** `nivel = f(pico histórico do saldo)`. O desconto morde o
   saldo e o progresso do ciclo, mas o nível NUNCA regride (lei 4: jamais streak-reset).
   Modelo híbrido: nível = história inteira; barra = ciclo de 12 semanas.

Duas decisões de modelagem que valem explicitar:

* **Dia sem fechamento (linha ausente em `routine_checks`) não é furo.** Não conta ganho
  nem furo — some do cálculo. É deliberado (lei 4: "dia quebrado = replanejar"): uma
  viagem, uma gripe, um dia que virou outra coisa não podem virar punição. Furo é um ato
  REGISTRADO — o dia teve fechamento e a rotina foi marcada como não-feita.

* **A janela de 7 dias do padrão É a semana ISO** (segunda a domingo, igual ao resto do
  código — ver `tasks.weekly_review_pack`). Uma semana ISO tem exatamente 7 dias, então a
  SPEC ("≥3 furos na mesma rotina numa janela de 7 dias") é atendida — e é a única leitura
  em que cada furo pertence a UMA semana só. Uma janela deslizante deixaria os mesmos três
  furos caírem em duas janelas de semanas diferentes e serem cobrados duas vezes, o que
  quebra a invariante 2 e a promessa de "desconta pouco". O teto é semanal; a janela também.
"""
from datetime import date, timedelta

from . import routines, store
from .config import settings

# `data` é TEXT ISO em routine_checks: qualquer data real é >= isto.
_INICIO_DOS_TEMPOS = "0001-01-01"


def segunda_da_semana(d: date) -> date:
    """A semana começa na segunda (mesma fronteira do resto do código). É a CHAVE de
    semana em todo este módulo — e o digest usa esta mesma função, não outra."""
    return d - timedelta(days=d.weekday())


def _data(valor: str) -> date | None:
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return None


def nomes_por_slug() -> dict[str, str]:
    """slug → nome de exibição. Inclui as INATIVAS: uma rotina soft-deletada continua
    dona dos checks antigos dela, e o histórico não pode virar slug cru na tela."""
    return {
        r["slug"]: r["nome"]
        for r in store.list_routines(incluir_inativas=True)
    }


# --- o núcleo: semanas -> ganho, furos, padrões, desconto --------------------


def _por_semana(checks: list[dict]) -> dict[date, dict]:
    """Agrupa os checks pela segunda-feira da semana ISO deles.

    Linha ausente não aparece aqui — logo, não vira ganho nem furo (ver docstring
    do módulo). Só o que foi REGISTRADO conta.
    """
    semanas: dict[date, dict] = {}
    for row in checks:
        d = _data(row["data"])
        if d is None:
            continue
        semana = semanas.setdefault(segunda_da_semana(d), {"feitos": 0, "furos": {}})
        if row["feito"]:
            semana["feitos"] += 1
        else:
            slug = row["rotina"]
            semana["furos"][slug] = semana["furos"].get(slug, 0) + 1
    return semanas


def _padroes(furos: dict[str, int], nomes: dict[str, str]) -> list[dict]:
    """Rotinas em padrão na semana, já com o desconto de cada uma alocado.

    Padrão = `routine_miss_threshold` furos ou mais (o limiar já existe na config —
    é o mesmo do digest, não se duplica número). Cada rotina em padrão custa
    `desconto_padrao` UMA vez; o total da semana é `min(teto, desconto_padrao × n)`.

    Como o teto pode cortar no meio, a alocação é greedy e determinística — mais furos
    primeiro, empate pelo slug — e cada rotina leva `min(desconto_padrao, o que sobrou
    do teto)`. Quem chega depois do teto esgotado leva delta 0: continua listada (é fato
    que está em padrão) e o digest diz a verdade, sem cobrar duas vezes.
    """
    limiar = max(1, settings.routine_miss_threshold)
    passo = max(0, settings.desconto_padrao)
    restante = max(0, settings.teto_desconto_semanal)

    em_padrao = sorted(
        ((slug, n) for slug, n in furos.items() if n >= limiar),
        key=lambda par: (-par[1], par[0]),
    )
    padroes = []
    for slug, n in em_padrao:
        delta = min(passo, restante)
        restante -= delta
        padroes.append({
            "slug": slug,
            "nome": nomes.get(slug, slug),
            "furos": n,
            "delta": -delta,
        })
    return padroes


def _semana(dados: dict | None, nomes: dict[str, str]) -> dict:
    """{ganho, desconto, saldo, padroes} de UMA semana. `None` = semana sem check."""
    if dados is None:
        return {"ganho": 0, "desconto": 0, "saldo": 0, "padroes": []}
    ganho = dados["feitos"] * max(0, settings.pontos_por_rotina)
    padroes = _padroes(dados["furos"], nomes)
    desconto = -sum(p["delta"] for p in padroes)
    return {
        "ganho": ganho,
        "desconto": desconto,
        "saldo": ganho - desconto,
        "padroes": padroes,
    }


def semana(ref: date | None = None) -> dict:
    """A semana ISO de `ref` (default: hoje). Usada pelo endpoint e pelo digest."""
    nomes = nomes_por_slug()
    semanas = _por_semana(store.get_checks_since(_INICIO_DOS_TEMPOS))
    return _semana(semanas.get(segunda_da_semana(ref or date.today())), nomes)


def padroes_por_semana() -> dict[date, dict[str, int]]:
    """{segunda: {slug: delta}} de toda a história. O digest usa isto pra dizer o
    desconto REAL de um padrão sem recalcular a regra por conta própria."""
    nomes = nomes_por_slug()
    return {
        seg: {p["slug"]: p["delta"] for p in _padroes(dados["furos"], nomes)}
        for seg, dados in _por_semana(
            store.get_checks_since(_INICIO_DOS_TEMPOS)
        ).items()
    }


# --- ciclo de 12 semanas (12WY) ----------------------------------------------


def _ciclo_semanas() -> int:
    return max(1, settings.ciclo_semanas)


def meta_do_ciclo() -> int:
    """Estimativa de uma semana cheia × `ciclo_semanas`.

    Uma rotina de quarta vale 1×/semana; uma de todo dia vale 7×. Rotina presa a um
    template (yoga/corrida) só aparece nos dias daquele template — como não existe
    calendário de templates, assumimos os templates equiprováveis e a ponderamos por
    `nº de templates dela / nº de templates`. É uma ESTIMATIVA da barra, não um contrato:
    o placar real vem sempre dos checks.
    """
    n_templates = len(routines.TEMPLATES) or 1
    por_semana = 0.0
    for r in store.list_routines():
        dias = (r.get("dias") or routines.TODOS).strip()
        n_dias = 7 if dias == routines.TODOS else len(
            [d for d in dias.split(",") if d.strip()]
        )
        templates = (r.get("templates") or routines.TODOS).strip()
        peso = 1.0 if templates == routines.TODOS else min(
            1.0,
            len([t for t in templates.split(",") if t.strip()]) / n_templates,
        )
        por_semana += n_dias * peso * max(0, settings.pontos_por_rotina)
    return round(por_semana * _ciclo_semanas())


# --- níveis vitalícios -------------------------------------------------------


def _limiares() -> list[int]:
    return sorted(settings.nivel_limiares)


def _nivel(pico: int) -> int:
    """Maior N cujo limiar ≤ pico histórico. Abaixo do 1º limiar = N0."""
    return sum(1 for limiar in _limiares() if pico >= limiar)


# --- o pacote que o app consome ----------------------------------------------


def resumo(hoje: date | None = None) -> dict:
    """Contrato do GET /pontos. Função pura de routine_checks + routines + config."""
    ref = hoje or date.today()
    nomes = nomes_por_slug()
    semanas = _por_semana(store.get_checks_since(_INICIO_DOS_TEMPOS))

    de = _ciclo_semanas()
    ancora = segunda_da_semana(_data(settings.ciclo_inicio) or ref)
    corrente = segunda_da_semana(ref)
    # Check gravado antes da âncora do ciclo entra no saldo/nível (a história é inteira),
    # mas não tem ciclo: cai no bloco 0, semana 1.
    decorridas = max(0, (corrente - ancora).days // 7)
    indice, dentro = divmod(decorridas, de)
    inicio_do_ciclo = ancora + timedelta(weeks=indice * de)

    saldo_total = 0
    pico_total = 0
    pontos_do_ciclo = 0
    for seg in sorted(semanas):
        saldo_da_semana = _semana(semanas[seg], nomes)["saldo"]
        saldo_total += saldo_da_semana
        pico_total = max(pico_total, saldo_total)
        if inicio_do_ciclo <= seg <= corrente:
            pontos_do_ciclo += saldo_da_semana

    nivel = _nivel(pico_total)
    limiares = _limiares()
    proximo = (
        None
        if nivel >= len(limiares)
        else {"n": nivel + 1, "faltam": max(0, limiares[nivel] - saldo_total)}
    )

    return {
        "nivel": nivel,
        "saldo_total": saldo_total,
        "pico_total": pico_total,
        "ciclo": {
            "indice": indice,
            "semana": dentro + 1,
            "de": de,
            "pontos": pontos_do_ciclo,
            "meta": meta_do_ciclo(),
        },
        "semana": _semana(semanas.get(corrente), nomes),
        "proximo_nivel": proximo,
    }
