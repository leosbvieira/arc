"""Tarefas por área + recência, e o digest (cobranças) portado do cutuca.

MOCK (default): lista canned em memória — reseta ao reiniciar. De propósito:
as tarefas REAIS moram no ClickUp (via Hermes), não aqui (glass-not-store, D-1).
REAL (HERMES_MOCK=false): pedir ao Hermes (profile Tarefas) via ClickUp MCP.

O digest (`run_digest`) aqui é o caminho DEV/MOCK e o fallback: o BFF calcula com as
regras do cutuca (cadence.py). Em produção com o Hermes, o cron calcula o digest e usa
POST /internal/notify (D-14). As regras de cadência são as mesmas nos dois casos.
"""

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time

from pydantic import BaseModel

from . import agenda, cadence, clickup_client, hermes_client, pontos, store, tz
from .config import settings

AREAS = ["Trabalho", "Staging", "Corpo", "Saúde Mental", "Responsabilidade",
         "Finance", "Carreira", "Estudo", "Relacionamentos", "Lazer"]


class Task(BaseModel):
    """Shape da API (o que o app recebe)."""

    id: str
    name: str
    area: str
    status: str = "open"
    due: str | None = None
    last_done: str | None = None
    assignee: str | None = None
    days_overdue: int | None = None   # positivo = atrasada; negativo = dias restantes (futura); None = sem due
    severity: str = "no_prazo"        # fonte única no back (cadence.tone_name)
    sensivel: bool = False            # marca por item (lei 7) — complementa a regra por área
    recorrente: bool = False          # tag `recorrente` no ClickUp — ver `_Task.recorrente`


@dataclass
class _Task:
    """Task interna com offsets relativos a hoje (cadência determinística)."""

    id: str
    name: str
    area: str
    status: str = "open"
    due_offset: int | None = None      # dias até vencer: 0=hoje, <0 atrasada, >0 futuro
    update_offset: int | None = None   # dias desde o último update (staleness)
    last_done: str | None = None       # rótulo de recência (hábitos), só exibição
    assignee: str | None = None
    sensivel: bool = False             # tag `sensivel` no ClickUp (lei 7)
    # Tag `recorrente` no ClickUp. É uma marca PARALELA à recorrência nativa, e não
    # por preguiça: a API v2 não devolve recorrência em lugar nenhum — nem em
    # `GET /list/{id}/task`, nem em `GET /task/{id}` (schema conferido em 09/ago).
    # O campo existe na UI web e não sai pela porta. Sem uma tag, o app não tem
    # como saber que a tarefa volta mês que vem, e "Unimed" concluída somes da
    # tela como se fosse uma tarefa qualquer.
    #
    # O preço é que as duas verdades podem descolar (desligar o recurring e
    # esquecer a tag deixa o app mentindo). Aceito: são 5 obrigações e o Leo é
    # dono dos dois lados. Se um dia for o BFF a gerar a próxima ocorrência, esta
    # tag vira a fonte única e o descolamento acaba junto.
    recorrente: bool = False

    # interface que cadence.py espera (mesma semântica do Task do cutuca)
    @property
    def days_overdue(self) -> int:
        return -self.due_offset if self.due_offset is not None else 0

    @property
    def days_until_due(self) -> int | None:
        return self.due_offset

    @property
    def days_since_update(self) -> int | None:
        return self.update_offset

    def due_label(self) -> str | None:
        if self.due_offset is None:
            return None
        if self.due_offset < 0:
            return f"atrasada {-self.due_offset}d"
        if self.due_offset == 0:
            return "vence hoje"
        return f"vence em {self.due_offset}d"


# seed do modo mock: áreas no vocabulário normativo das 10 listas (Task 6); senão
# `_grouped` (que itera AREAS) não acha essas tarefas e o modo dev mostra só "Trabalho".
_MOCK: list[_Task] = [
    _Task("t1", "Relatório mensal", "Trabalho", due_offset=0, assignee="Ana"),
    _Task("t2", "Pagar fatura do cartão", "Finance", due_offset=-2),
    _Task("t3", "Dentista", "Corpo", last_done="há 7 meses"),
    _Task("t4", "Treino", "Corpo", due_offset=0),
    _Task("t5", "Ligar pro contador", "Responsabilidade", update_offset=5),
    _Task("t6", "Renovar seguro do carro", "Finance", due_offset=-8),
]
_next = 7
# `_Task` não tem descrição (é o shape que o app recebe), e o resumão precisa dela
# para o marker sobreviver no modo mock — sem isto, reconciliar nunca acharia nada
# fora do ClickUp real, e o caminho mais perigoso ficaria sem teste.
_MOCK_DESCRICOES: dict[str, str] = {}


def _display(t: _Task) -> Task:
    due = t.due_label()
    if due is None and t.update_offset is not None and t.update_offset >= 1:
        due = f"parada há {t.update_offset}d"
    # due_offset é dias até vencer (negativo = atrasada); days_overdue inverte o sinal
    # (positivo = atrasada), None quando não há due. Ponto único: todas as rotas e
    # ambas as fontes (mock/ClickUp) passam por aqui, então a severidade nasce uma vez.
    days_overdue = -t.due_offset if t.due_offset is not None else None
    return Task(
        id=t.id,
        name=t.name,
        area=t.area,
        status=t.status,
        due=due,
        last_done=t.last_done,
        assignee=t.assignee,
        days_overdue=days_overdue,
        severity=cadence.tone_name(days_overdue),
        sensivel=t.sensivel,
        recorrente=t.recorrente,
    )


def _open() -> list[_Task]:
    return [t for t in _MOCK if t.status == "open"]


def _use_clickup() -> bool:
    return settings.tasks_source == "clickup" and bool(settings.clickup_token)


def _from_clickup(t: dict) -> _Task:
    """ClickUp task JSON -> _Task interno.

    update_offset fica None nesta 1ª versão: só cobramos por vencimento (due). O nudge
    por 'parada há Xd' (staleness) a gente liga depois de ver os dados reais, senão
    inunda a Revisão com tudo que não foi tocado em 3 dias.
    """
    status = (t.get("status") or {}).get("status")
    assignees = t.get("assignees") or []
    # As tags são normalizadas com _norm: `sensivel` e `sensível` contam igual (lei 7),
    # e o mesmo vale pra `recorrente`.
    marcas = {
        _norm(tag.get("name", "") if isinstance(tag, dict) else str(tag))
        for tag in (t.get("tags") or [])
    }
    return _Task(
        id=str(t["id"]),
        name=t.get("name", ""),
        area=t.get("_area", "Staging"),
        status=status or "open",
        due_offset=clickup_client.days_from_ms(t.get("due_date")),
        update_offset=None,
        assignee=(assignees[0].get("username") if assignees else None),
        sensivel="sensivel" in marcas,
        recorrente="recorrente" in marcas,
    )


def _grouped(tasks: list[_Task]) -> dict:
    areas = []
    for area in AREAS:
        items = [_display(t).model_dump() for t in tasks if t.area == area]
        if items:
            areas.append({"area": area, "tasks": items})
    return {"areas": areas}


async def list_by_area() -> dict:
    if _use_clickup():
        return _grouped([_from_clickup(t) for t in await clickup_client.fetch_open()])
    return _grouped(_open())


async def create(
    name: str,
    area: str,
    due_ts: float | None = None,
    com_hora: bool = True,
) -> Task:
    if _use_clickup():
        criado = await clickup_client.create(
            name,
            area,
            due_ts=due_ts,
            due_date_time=com_hora,
        )
        return _display(_from_clickup(criado))
    # O mock mantém o contrato histórico: due é integração externa, não estado local.
    global _next
    t = _Task(f"t{_next}", name, area, due_offset=0)
    _next += 1
    _MOCK.append(t)
    return _display(t)


async def adiar(task_id: str, due_ts: float, novo_offset: int) -> Task | None:
    """Remarca o prazo. Lei 4: replanejar não é envergonhar — sem isto, a única forma
    de calar uma cobrança é concluir mentindo, o que polui pontos e review."""
    if _use_clickup():
        if not await clickup_client.set_due(task_id, due_ts):
            return None
        store.log_event("task_adiada", ref=task_id)
        src, _ = await _source()
        for t in src:
            if t.id == task_id:
                return _display(t)
        return None
    for t in _MOCK:
        if t.id == task_id:
            t.due_offset = novo_offset
            store.log_event("task_adiada", ref=task_id)
            return _display(t)
    return None


async def complete(task_id: str) -> bool:
    if _use_clickup():
        ok = await clickup_client.complete(task_id)
        if ok:
            store.log_event("task_completed", ref=task_id)
        return ok
    for t in _MOCK:
        if t.id == task_id:
            t.status = "done"
            store.log_event("task_completed", ref=task_id)
            return True
    return False


def _scorecard(checks: list[dict]) -> dict:
    """Agrega checks por rotina; semanal e mensal compartilham esta mesma regra."""
    por_rotina: dict[str, dict] = {}
    for row in checks:
        item = por_rotina.setdefault(
            row["rotina"],
            {"feitos": 0, "dias": 0},
        )
        item["dias"] += 1
        item["feitos"] += 1 if row["feito"] else 0

    pct = (
        round(
            100
            * sum(item["feitos"] / item["dias"] for item in por_rotina.values())
            / len(por_rotina)
        )
        if por_rotina
        else 0
    )
    return {"pct": pct, "por_rotina": por_rotina}


def weekly_review_pack(today: str | None = None) -> dict:
    """Números da semana ISO corrente, com fronteira local em America/Sao_Paulo."""
    from datetime import date, datetime, time, timedelta

    local_tz = tz.TZ
    ref = date.fromisoformat(today) if today else datetime.now(local_tz).date()
    monday = ref - timedelta(days=ref.weekday())
    since_iso = monday.isoformat()
    since_ts = datetime.combine(monday, time.min, tzinfo=local_tz).timestamp()

    checks_da_semana = store.get_checks_since(since_iso)
    scorecard = _scorecard(checks_da_semana)
    sessoes = [
        session
        for session in store.list_sessions_since(since_ts)
        if session["tipo"] == "leitura"
    ]
    iso_week = ref.isocalendar()

    # Uma leitura histórica é compartilhada por todos os objetivos ligados a rotina.
    from . import objetivos as objetivos_dominio

    checks_dos_objetivos = store.get_checks_since("0001-01-01")
    objetivos_semana = []
    for objetivo in store.list_objetivos():
        marcas = (
            []
            if objetivo.get("rotina_slug")
            else store.marcas_do_objetivo(objetivo["id"])
        )
        atual = objetivos_dominio.progresso(
            objetivo,
            checks_dos_objetivos,
            marcas,
            ref,
        )["semana_atual"]
        objetivos_semana.append({
            "nome": objetivo["nome"],
            "n_semana": atual["n"],
            "alvo": atual["alvo"],
            "pct": atual["pct"],
        })

    aprendizados_novos = store.list_aprendizados(status="novo")
    # Só a prática DESTA semana conta como "a prática da semana": sem o filtro, uma
    # escolha de julho seguia anunciada em agosto.
    praticas = [p for p in [store.pratica_da_semana(agenda.semana_iso(ref))] if p]

    # `paradas` exclui as de alvo `app` de propósito: aquelas dependem de uma
    # sessão de programação, não de uma decisão dele no domingo. Contá-las aqui
    # transformaria a fila numa dívida crescente — a inversão de incentivo de novo.
    #
    # E a escolhida é filtrada pela semana pelo MESMO motivo do bloco acima: sem o
    # filtro, uma escolha de junho seguia servida como "a desta semana" e, porque a
    # tela usa ternário encadeado, o convite "escolher 1" nunca mais aparecia.
    semana_ref = agenda.semana_iso(ref)
    a_triar = store.melhorias_a_triar()
    escolhiveis = store.melhorias_escolhiveis()
    return {
        "week": f"{iso_week.year}-W{iso_week.week:02d}",
        "desde": since_iso,
        "scorecard": scorecard,
        "objetivos": objetivos_semana,
        "edificacao": {
            "novos": len(aprendizados_novos),
            "pratica": praticas[0] if praticas else None,
        },
        "melhorias": {
            "paradas": len(a_triar) + len(escolhiveis),
            "a_triar": len(a_triar),
            "escolhiveis": len(escolhiveis),
            "escolhida": store.melhoria_da_semana(semana_ref),
            "vencidas": store.melhorias_vencidas(semana_ref),
            "app": len(store.list_melhorias(alvo="app", status="novo")),
        },
        "dailies": store.count_events_since("closing_approved", since_ts),
        "capturas": store.count_events_since("capture_done", since_ts),
        "sessoes_leitura": {
            "n": len(sessoes),
            "min_total": sum(session["duracao_s"] for session in sessoes) // 60,
        },
        "tarefas_concluidas": None,
        "staging_pendentes": None,
    }


def is_primeiro_domingo(ref: date) -> bool:
    """Primeiro domingo é o domingo que ainda cai nos sete primeiros dias."""
    return ref.weekday() == 6 and ref.day <= 7


def monthly_review_pack(today: str | None = None) -> dict:
    """Números finais do mês civil anterior, em America/Sao_Paulo."""
    from datetime import datetime, time, timedelta

    local_tz = tz.TZ
    ref = date.fromisoformat(today) if today else datetime.now(local_tz).date()

    inicio_mes_atual = ref.replace(day=1)
    fim = inicio_mes_atual - timedelta(days=1)
    inicio = fim.replace(day=1)

    inicio_iso = inicio.isoformat()
    fim_iso = fim.isoformat()
    since_ts = datetime.combine(
        inicio,
        time.min,
        tzinfo=local_tz,
    ).timestamp()
    until_ts = datetime.combine(
        inicio_mes_atual,
        time.min,
        tzinfo=local_tz,
    ).timestamp()

    # get_checks_since não possui limite final; a comparação ISO fecha a janela.
    checks = [
        row
        for row in store.get_checks_since(inicio_iso)
        if row["data"] <= fim_iso
    ]
    sessoes = [
        session
        for session in store.list_sessions_since(since_ts, until_ts)
        if session["tipo"] == "leitura"
    ]

    objetivos_do_mes = []
    for objetivo in store.list_objetivos():
        rotina_slug = objetivo.get("rotina_slug")
        if rotina_slug:
            datas = {
                row["data"]
                for row in checks
                if row["rotina"] == rotina_slug and bool(row["feito"])
            }
        else:
            datas = {
                marcada_em
                for marcada_em in store.marcas_do_objetivo(objetivo["id"])
                if inicio_iso <= marcada_em <= fim_iso
            }

        objetivos_do_mes.append({
            "nome": objetivo["nome"],
            "total_no_mes": len(datas),
        })

    return {
        "mes": inicio.strftime("%Y-%m"),
        "scorecard": _scorecard(checks),
        "dailies": store.count_events_since(
            "closing_approved",
            since_ts,
            until_ts,
        ),
        "capturas": store.count_events_since(
            "capture_done",
            since_ts,
            until_ts,
        ),
        "sessoes_leitura": {
            "n": len(sessoes),
            "min_total": sum(
                session["duracao_s"]
                for session in sessoes
            ) // 60,
        },
        "pontos": pontos.resumo_periodo(inicio, fim),
        "objetivos": objetivos_do_mes,
        "patrimonio": (
            "preencher a nota mensal de patrimônio no vault (manual)"
        ),
    }


def monthly_review_text(today: str | None = None) -> str:
    """Texto factual do bloco mensal fundido ao review do primeiro domingo."""
    pack = monthly_review_pack(today)
    objetivos_texto = " · ".join(
        f"{objetivo['nome']} {objetivo['total_no_mes']}"
        for objetivo in pack["objetivos"]
    )

    return (
        f"mês {pack['mes']} · scorecard {pack['scorecard']['pct']}%\n"
        f"pontos: +{pack['pontos']['ganho']} "
        f"−{pack['pontos']['desconto']}\n"
        f"dailies {pack['dailies']} · capturas {pack['capturas']} · "
        f"leitura {pack['sessoes_leitura']['n']} sessões "
        f"({pack['sessoes_leitura']['min_total']} min)\n"
        f"objetivos: {objetivos_texto or 'sem objetivos ativos'}\n"
        f"🏦 patrimônio: {pack['patrimonio']}"
    )


def weekly_review_text(today: str | None = None) -> str:
    """Texto compacto do nudge semanal; métricas ClickUp ficam no endpoint."""
    pack = weekly_review_pack(today)
    rotinas = " · ".join(
        f"{rotina} {dados['feitos']}/{dados['dias']}"
        for rotina, dados in sorted(
            pack["scorecard"]["por_rotina"].items(),
        )
    )
    texto = (
        f"semana {pack['week']} — scorecard {pack['scorecard']['pct']}%\n"
        f"{rotinas or 'sem checks registrados'}\n"
        f"dailies {pack['dailies']}/7 · capturas {pack['capturas']} · "
        f"leitura {pack['sessoes_leitura']['n']} sessões "
        f"({pack['sessoes_leitura']['min_total']} min)"
    )
    novos = pack["edificacao"]["novos"]
    if novos:
        texto += (
            f"\nedificação: {novos} aprendizados sem prática "
            "— escolher 1 no review"
        )

    # Linhas com pesos diferentes: `escolhiveis` pede uma decisão dele, `a_triar`
    # pede um toque, `app` é só informação. Misturar tudo num número só cobraria o
    # que ele não tem como fazer sozinho — e prometeria uma ação que a tela de
    # destino não oferece naquela seção.
    #
    # ⚠️ Lei 7: este texto vira artefato no vault E corpo de nudge, e o corpo
    # inteiro do nudge aparece no lockscreen. Aqui só entra CONTAGEM e semana —
    # o texto da melhoria fica no pack, que só sai por /review/weekly (atrás do login).
    melhorias = pack["melhorias"]
    escolhiveis = melhorias["escolhiveis"]
    a_triar = melhorias["a_triar"]
    if escolhiveis:
        plural = "melhoria parada" if escolhiveis == 1 else "melhorias paradas"
        texto += f"\nmelhorias: {escolhiveis} {plural} — escolher 1 no review"
    if a_triar:
        plural = "melhoria a triar" if a_triar == 1 else "melhorias a triar"
        texto += f"\nmelhorias: {a_triar} {plural} — um toque cada"
    # UMA linha, nunca N: uma lista que cresce a cada semana sem resposta vira
    # dívida, e dívida é justamente o que faz ele parar de abrir a tela.
    # Lei 4: constata a semana, não julga o que não aconteceu.
    vencidas = melhorias["vencidas"]
    if len(vencidas) == 1:
        texto += (
            f"\nmelhoria escolhida em {vencidas[0]['escolhida_semana']} segue em aberto"
        )
    elif vencidas:
        texto += f"\n{len(vencidas)} melhorias escolhidas antes seguem em aberto"
    if melhorias["app"]:
        texto += f"\nmelhorias de app: {melhorias['app']} pro Claude"
    return texto


# --- digest v2 (C10/C11 + lei 7) --------------------------------------------
# O texto INTEIRO da mensagem do Telegram aparece no lockscreen, então linhas de áreas
# sensíveis saem neutralizadas nesse canal; o app (atrás do login) mostra tudo. O digest
# envia se houver QUALQUER linha acionável (tarefa, staging, rotina ou captura travada).

MARKER = {"no_prazo": "🟡", "leve": "🟠", "firme": "🔴", "urgente": "🚨"}


def _norm(s: str) -> str:
    """Fold p/ comparação robusta de área (lei 7 FAIL-CLOSED): drift de caixa/acento/espaço
    entre o nome da lista no ClickUp e o CSV de config não pode vazar conteúdo no lockscreen.
    NFKD → remove marcas de acento → casefold → strip."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.casefold().strip()


def _sensitive_areas() -> set[str]:
    return {_norm(a) for a in settings.sensitive_areas.split(",") if a.strip()}


def eh_sensivel(area: str) -> bool:
    """Lei 7 FAIL-CLOSED: a área é sensível? Ponto único da regra — o digest e a camada
    de notificação (notify.py) perguntam AQUI, ninguém reimplementa a dobra."""
    return _norm(area or "") in _sensitive_areas()


# O preview (lockscreen do Telegram, corpo do push) é a superfície que qualquer um vê
# sem destravar o telefone. Item sensível vira ISTO — fato de que existe algo, zero
# conteúdo, e ainda acionável. Mesma promessa da linha neutra do digest.
NEUTRO = "1 item sensível — abre o app"


def neutralizar(texto: str, *, sensivel: bool = False) -> str:
    """O corpo que vai pro preview. `sensivel=True` → nada de conteúdo (lei 7)."""
    return NEUTRO if sensivel else texto


def render_digest_lines(tasks: list[Task], for_channel: str) -> list[str]:
    """for_channel: 'telegram' neutraliza áreas sensíveis E itens marcados (lei 7);
    'app' mostra tudo. A marca por item complementa a regra por área — qualquer
    uma das duas basta para neutralizar."""
    lines = []
    for t in sorted(tasks, key=lambda x: -(x.days_overdue or 0)):
        m = MARKER.get(t.severity, "🟡")
        atraso = f"{t.days_overdue}d de atraso" if (t.days_overdue or 0) > 0 else "no prazo"
        if for_channel == "telegram" and (eh_sensivel(t.area) or t.sensivel):
            lines.append(f"{m} 1 pendência de saúde ({atraso}) — abre o app")
        else:
            safe_name = t.name.replace(chr(10), " ")
            lines.append(f"{m} {safe_name} · {t.area} ({atraso})")
    return lines


def staging_line(count: int, oldest_days: int | None) -> str | None:
    if count and oldest_days is not None and oldest_days >= settings.staging_age_days:
        return f"📥 staging: {count} itens, mais velho {oldest_days}d — triar no ClickUp"
    return None


def routine_lines(today: str | None = None) -> list[str]:
    """Furo = dia COM fechamento e check false; >=N/7d vira padrão. Linguagem factual (lei 4).

    A linha diz o NOME da rotina (o slug é chave interna, não texto de tela) e anexa o
    desconto que o padrão REALMENTE custou — fato + número, jamais julgamento. O desconto
    vem do motor de pontos (`pontos.py`), nunca recalculado aqui: o digest não pode
    prometer um número que o placar não cobra.

    O desconto é procurado na semana do ÚLTIMO furo da janela — que é a semana que cobrou
    aquele padrão (o motor cobra por semana ISO, 1x por rotina). Três casos, todos verdade:
      · cobrou            → "3 furos em 7d. −3 pts."
      · teto já esgotado  → "4 furos em 7d. (teto semanal atingido, sem desconto)"
      · não virou padrão em nenhuma semana (os furos se dividem entre duas semanas e
        nenhuma delas chegou ao limiar) → só o fato, sem falar de pontos.
    """
    from datetime import date, timedelta

    from . import pontos

    ref = date.fromisoformat(today) if today else pontos.hoje_local()
    since = (ref - timedelta(days=7)).isoformat()

    misses: dict[str, int] = {}
    ultimo_furo: dict[str, date] = {}
    for row in store.get_checks_since(since):
        if row["feito"]:
            continue
        slug = row["rotina"]
        d = date.fromisoformat(row["data"])
        misses[slug] = misses.get(slug, 0) + 1
        ultimo_furo[slug] = max(d, ultimo_furo.get(slug, d))

    nomes = pontos.nomes_por_slug()
    deltas = pontos.padroes_por_semana()

    linhas = []
    for slug, n in sorted(misses.items()):
        if n < settings.routine_miss_threshold:
            continue
        semana = deltas.get(pontos.segunda_da_semana(ultimo_furo[slug]), {})
        delta = semana.get(slug)
        if delta is None:
            custo = ""
        elif delta < 0:
            custo = f" −{-delta} pts."
        else:
            custo = " (teto semanal atingido, sem desconto)"
        linhas.append(f"🔁 {nomes.get(slug, slug)}: {n} furos em 7d.{custo}")
    return linhas


def _age_days(ms) -> int | None:
    """Idade em dias desde a criação. ClickUp date_created é epoch-ms UTC — comparamos os
    DOIS lados em UTC (não `date.today()` local) pra não ter skew de fronteira de dia, e o
    parse fica independente da tz da máquina. Valor ausente/não-numérico → None."""
    from datetime import datetime, timezone
    if ms in (None, "", 0, "0"):
        return None
    try:
        created = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    return (datetime.now(timezone.utc).date() - created).days


def _staging_metrics(raw: list[dict], area: str) -> tuple[int, int | None]:
    """(qtd, idade-do-mais-velho-em-dias) da lista Staging. Degrada p/ (0, None) enquanto
    a lista não existir no ClickUp (Task 6): `area` não está em AREA_LISTS, logo fetch_open
    nem a traz. Idade por `date_created`."""
    if area not in clickup_client.AREA_LISTS:
        return 0, None
    items = [t for t in raw if t.get("_area") == area]
    ages = [a for a in (_age_days(t.get("date_created")) for t in items) if a is not None]
    return len(items), (max(ages) if ages else None)


async def run_digest() -> dict:
    """Digest v2: cobranças por área (staging excluído) + staging envelhecendo + rotina-
    padrão + capturas travadas. Dois corpos — `body_telegram` neutraliza áreas sensíveis
    (lei 7), `body_app` mostra tudo — mais a lista `tasks` (fresca p/ a Home)."""
    staging = clickup_client.STAGING
    staging_count, staging_oldest = 0, None
    if _use_clickup():
        raw = await clickup_client.fetch_open()
        src = [_from_clickup(t) for t in raw]
        staging_count, staging_oldest = _staging_metrics(raw, staging)
    else:
        src = _open()

    selected = [t for t in cadence.select(src) if t.area != staging]
    tasks = [_display(t) for t in selected]

    extra: list[str] = []
    sl = staging_line(staging_count, staging_oldest)
    if sl:
        extra.append(sl)
    extra.extend(routine_lines())
    try:
        from datetime import date

        from . import agenda

        extra.extend(agenda.linhas_digest(await agenda.do_dia(date.today())))
    except Exception:
        # A agenda é best-effort: uma fonte externa não cala a cobrança factual (lei 4).
        pass
    n_failed = len(store.failed_captures())
    if n_failed:
        extra.append(f"⚠ {n_failed} capturas não processadas — abrir o app")

    # A prática da semana (edificação) lembra diariamente. lines_extra mantém a
    # versão completa destinada ao app; só o corpo do Telegram recebe a variante
    # neutra quando o aprendizado é sensível (lei 7).
    extra_telegram = list(extra)
    pratica = store.pratica_da_semana(agenda.semana_iso(tz.hoje_local()))
    if pratica is not None:
        texto = str(pratica["texto"]).replace(chr(10), " ")
        extra.append(f"🧭 prática da semana: {texto}")
        if bool(pratica["sensivel"]):
            extra_telegram.append("🧭 prática da semana definida — abre o app")
        else:
            extra_telegram.append(f"🧭 prática da semana: {texto}")

    body_telegram = "\n".join(
        [*render_digest_lines(tasks, "telegram"), *extra_telegram]
    )
    body_app = "\n".join([*render_digest_lines(tasks, "app"), *extra])
    return {"tasks": tasks, "body_telegram": body_telegram,
            "body_app": body_app, "lines_extra": extra}


# --- os dois ritos (P2 itens 5 e 6): abertura do dia e Shutdown das 19h -------
# Aqui não se renderiza TEXTO: estes dois devolvem DADO, porque quem desenha é o app.
# (O digest, acima, é o contrário — ele existe para virar mensagem.)

AGUARDANDO = "aguardando"   # a tag que o pipeline de captura põe numa cobrança


def _tags(t: dict) -> set[str]:
    """Nomes das tags de uma task do ClickUp, dobrados (a tag é digitada por humano)."""
    return {
        _norm(tag.get("name") or "")
        for tag in (t.get("tags") or [])
        if isinstance(tag, dict)
    }


async def _source() -> tuple[list[_Task], list[dict]]:
    """(tarefas internas, json cru do ClickUp). O cru é o que carrega tag e date_created —
    campos que o _Task não guarda e que os ritos precisam."""
    if _use_clickup():
        raw = await clickup_client.fetch_open()
        return [_from_clickup(t) for t in raw], raw
    return _open(), []


async def due_hoje() -> list[dict]:
    """As tarefas que HOJE cobra: vencendo hoje e as já vencidas (uma atrasada continua
    sendo coisa de hoje). Sem due → não é pauta da manhã, é backlog."""
    src, _ = await _source()
    return [
        _display(t).model_dump()
        for t in src
        if t.due_offset is not None and t.due_offset <= 0
    ]


# --- triagem em lote do Staging (P2 item 13) ----------------------------------
# Lei 3: a IA só PROPÕE (triagem_pack); mover é sempre um POST explícito do Leo
# (aplicar_triagem). Um item ruim nunca aborta o lote.

AREAS_TRIAGEM = [area for area in AREAS if area != clickup_client.STAGING]


async def triagem_pack() -> dict:
    """Monta os itens do Staging com propostas, nunca decisões, de destino.

    **A proposta é LIDA, não calculada.** Ela foi decidida uma vez, quando a
    captura passou pelo pipeline e o Hermes já estava lendo aquele texto para
    achar tipo e título (`hermes_client.classify`). Antes disto a rota
    reclassificava o lote inteiro a cada abertura da tela — 11,6s medidos em
    09/ago, gastos para produzir sempre a mesma resposta, num caminho em que o
    Leo está parado esperando. Agora a rota é leitura de banco.

    Item sem proposta é o caso normal, não erro: entrou no Staging por fora da
    captura (criado à mão no ClickUp) ou é anterior à coluna. Ele aparece sem
    sugestão e o Leo escolhe — que é exatamente o que acontecia quando o Hermes
    estava fora do ar.
    """
    src, raw = await _source()
    itens_staging = [
        tarefa for tarefa in src if tarefa.area == clickup_client.STAGING
    ]
    raw_por_id = {
        item.get("id"): item
        for item in raw
        if isinstance(item, dict) and item.get("id") is not None
    }

    propostas = store.areas_propostas_por_task()

    itens = []
    for tarefa in itens_staging:
        area_proposta = propostas.get(tarefa.id)
        if area_proposta not in AREAS_TRIAGEM:
            area_proposta = None

        item_raw = raw_por_id.get(tarefa.id, {})
        itens.append(
            {
                "id": tarefa.id,
                "name": tarefa.name,
                "idade_d": _age_days(item_raw.get("date_created")),
                "area_proposta": area_proposta,
            }
        )

    return {"itens": itens, "n": len(itens)}


async def _marcar_prazo(task_id: str, due: str | None) -> str | None:
    """`None` = ele não pediu prazo. `"ok"`/`"falhou"` = pediu, e este é o desfecho.

    A exceção morre aqui de propósito: o movimento já aconteceu e não tem desfazer,
    então deixar o erro subir marcaria como NÃO MOVIDA uma tarefa que moveu — e ele
    triaria de novo o que já triou.
    """
    if due is None:
        return None
    try:
        return "ok" if await clickup_client.set_due(task_id, _timestamp_do_prazo(due)) else "falhou"
    except Exception:
        return "falhou"


def _timestamp_do_prazo(due: str) -> float:
    """Data civil → instante local. Mesma conversão do POST /tasks e do adiar: a
    validação do formato mora no modelo da rota, aqui só chega data já conferida."""
    return datetime.combine(date.fromisoformat(due), time.min, tzinfo=tz.TZ).timestamp()


async def criar_resumao_de_obra(*, nome: str, descricao: str) -> str | None:
    """Cria a tarefa de resumão no Staging e devolve o id do ClickUp.

    Vai para o Staging, não direto para uma área: lei 3, o sistema propõe e ele
    decide onde mora e quando faz. É o mesmo caminho da captura.
    """
    if _use_clickup():
        criada = await clickup_client.create(
            nome,
            clickup_client.STAGING,
            description=descricao,
        )
        task_id = criada.get("id")
        return str(task_id) if task_id is not None else None

    global _next
    tarefa = _Task(f"t{_next}", nome, clickup_client.STAGING)
    _next += 1
    _MOCK.append(tarefa)
    _MOCK_DESCRICOES[tarefa.id] = descricao
    return tarefa.id


async def achar_resumao_de_obra(marker: str) -> str | None:
    """Procura o resumão pelo marker. `None` é PROVA de ausência, não "não sei" —
    quem chama libera a obra com base nisso, então falha de rede tem que estourar,
    nunca virar `None`."""
    if _use_clickup():
        return await clickup_client.find_task_by_marker(
            clickup_client.AREA_LISTS[clickup_client.STAGING],
            marker,
        )
    for task_id, descricao in _MOCK_DESCRICOES.items():
        if marker in descricao and any(item.id == task_id for item in _MOCK):
            return task_id
    return None


async def aplicar_triagem(
    movimentos: list[tuple[str, str, str | None]],
) -> list[dict]:
    """Aplica movimentos aprovados pelo Leo, isolando falhas por tarefa.

    Cada item é conferido novamente no Staging imediatamente antes do movimento;
    assim, uma proposta antiga não move uma tarefa que já saiu da triagem.

    O prazo é opcional e vem DEPOIS do movimento, num campo próprio do resultado:
    triar diz onde a tarefa mora, e uma data que falha não pode desfazer — nem
    esconder — a decisão de área, que é a parte cara do gesto.
    """
    resultados: list[dict] = []

    if _use_clickup():
        for task_id, area, due in movimentos:
            try:
                task = await clickup_client.get_task(task_id)
                task_list = task.get("list")
                esta_no_staging = isinstance(task_list, dict) and (
                    task_list.get("name") == clickup_client.STAGING
                    or task_list.get("id")
                    == clickup_client.AREA_LISTS[clickup_client.STAGING]
                )
                if not esta_no_staging:
                    resultados.append(
                        {
                            "task_id": task_id,
                            "ok": False,
                            "erro": "fora_do_staging",
                            "prazo": None,
                        }
                    )
                    continue

                await clickup_client.move_task(
                    task_id,
                    clickup_client.AREA_LISTS[area],
                )
                resultados.append(
                    {
                        "task_id": task_id,
                        "ok": True,
                        "erro": None,
                        "prazo": await _marcar_prazo(task_id, due),
                    }
                )
            except Exception as exc:
                # Apenas a classe é exposta: mensagens podem carregar conteúdo remoto.
                resultados.append(
                    {
                        "task_id": task_id,
                        "ok": False,
                        "erro": type(exc).__name__,
                        "prazo": None,
                    }
                )
    else:
        for task_id, area, due in movimentos:
            tarefa = next(
                (item for item in _MOCK if item.id == task_id),
                None,
            )
            if tarefa is None:
                resultados.append(
                    {
                        "task_id": task_id,
                        "ok": False,
                        "erro": "nao_encontrado",
                        "prazo": None,
                    }
                )
                continue
            if tarefa.area != clickup_client.STAGING:
                resultados.append(
                    {
                        "task_id": task_id,
                        "ok": False,
                        "erro": "fora_do_staging",
                        "prazo": None,
                    }
                )
                continue

            tarefa.area = area
            if due is not None:
                tarefa.due = due
            resultados.append(
                {
                    "task_id": task_id,
                    "ok": True,
                    "erro": None,
                    "prazo": None if due is None else "ok",
                }
            )

    movidos = sum(1 for resultado in resultados if resultado["ok"])
    store.log_event(
        "triagem_aplicada",
        meta={
            "n": movidos,
            "erros": len(resultados) - movidos,
        },
    )
    return resultados


def _follow_up_do_scheduler(item: dict) -> dict:
    """Item de hora marcada no shape de tarefa (o app renderiza UMA lista de follow-ups).
    `id` prefixado e `origem` explícita: isto NÃO é uma task do ClickUp e não pode ser
    mandado pro POST /tasks/{id}/complete."""
    return {
        "id": f"sched-{item['id']}",
        "name": item["ref"],
        "area": "Aguardando",
        "status": "open",
        "due": None,
        "last_done": None,
        "assignee": None,
        "days_overdue": None,
        "severity": cadence.tone_name(None),
        "origem": "scheduler",
        "quando": item["quando"],
    }


async def shutdown_pack() -> dict:
    """Os dados do Shutdown (A2/19h): o que fica aberto no trabalho, o que está esperando
    resposta de terceiro e o tamanho da fila de triagem.

    `staging` é DADO, não a linha de texto do digest (`staging_line`): a mesma métrica,
    duas superfícies. E o gate de idade (`staging_age_days`) NÃO se aplica aqui — o digest
    só cobra staging quando envelhece; o Shutdown mostra o número sempre, é um painel.
    """
    src, raw = await _source()

    trabalho = [
        _display(t).model_dump() | {"origem": "clickup"}
        for t in src
        if t.area == "Trabalho"
    ]

    por_id = {str(t.get("id")): t for t in raw}
    follow_ups = [
        _display(t).model_dump() | {"origem": "clickup"}
        for t in src
        if AGUARDANDO in _tags(por_id.get(t.id, {}))
    ]
    follow_ups += [_follow_up_do_scheduler(i) for i in store.pending_schedules()]

    n, mais_velho = _staging_metrics(raw, clickup_client.STAGING)
    return {
        "trabalho_aberto": trabalho,
        "follow_ups": follow_ups,
        "staging": {"n": n, "mais_velho_d": mais_velho},
    }


async def get_detail(task_id: str) -> dict | None:
    """Detalhe de 1 tarefa (com descrição) pro app abrir ao tocar.

    Fail-closed: uma tarefa fora das listas próprias não é exposta pelo BFF.
    """
    if _use_clickup():
        t = await clickup_client.get_task(task_id)
        lst = t.get("list") or {}
        list_id = str(lst.get("id"))
        if list_id not in clickup_client.AREA_LISTS.values():
            return None
        t["_area"] = clickup_client.LIST_AREA[list_id]
        base = _display(_from_clickup(t)).model_dump()
        base["priority"] = (t.get("priority") or {}).get("priority") if t.get("priority") else None
        base["description"] = (t.get("text_content") or t.get("description") or "").strip()
        base["url"] = t.get("url")
        return base
    for t in _MOCK:
        if t.id == task_id:
            base = _display(t).model_dump()
            base.update(priority=None, description="", url=None)
            return base
    return None
