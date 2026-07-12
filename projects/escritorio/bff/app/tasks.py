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
from datetime import date

from pydantic import BaseModel

from . import cadence, clickup_client, pontos, store
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
    return _Task(
        id=str(t["id"]),
        name=t.get("name", ""),
        area=t.get("_area", "Staging"),
        status=status or "open",
        due_offset=clickup_client.days_from_ms(t.get("due_date")),
        update_offset=None,
        assignee=(assignees[0].get("username") if assignees else None),
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
    from zoneinfo import ZoneInfo

    local_tz = ZoneInfo("America/Sao_Paulo")
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

    return {
        "week": f"{iso_week.year}-W{iso_week.week:02d}",
        "desde": since_iso,
        "scorecard": scorecard,
        "objetivos": objetivos_semana,
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
    from zoneinfo import ZoneInfo

    local_tz = ZoneInfo("America/Sao_Paulo")
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
    return (
        f"semana {pack['week']} — scorecard {pack['scorecard']['pct']}%\n"
        f"{rotinas or 'sem checks registrados'}\n"
        f"dailies {pack['dailies']}/7 · capturas {pack['capturas']} · "
        f"leitura {pack['sessoes_leitura']['n']} sessões "
        f"({pack['sessoes_leitura']['min_total']} min)"
    )


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
    """for_channel: 'telegram' neutraliza áreas sensíveis (lei 7); 'app' mostra tudo."""
    lines = []
    for t in sorted(tasks, key=lambda x: -(x.days_overdue or 0)):
        m = MARKER.get(t.severity, "🟡")
        atraso = f"{t.days_overdue}d de atraso" if (t.days_overdue or 0) > 0 else "no prazo"
        if for_channel == "telegram" and eh_sensivel(t.area):
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

    ref = date.fromisoformat(today) if today else date.today()
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

    body_telegram = "\n".join([*render_digest_lines(tasks, "telegram"), *extra])
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
