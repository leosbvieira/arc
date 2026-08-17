"""Fonte única dos horários dos ritos.

Antes deste módulo os horários viviam em CINCO lugares e nenhum era autoritativo:
o gatilho do Agendador (`install-cron.ps1`), o texto do push (`NUDGE_COPY`), e as
telas (`mesaView.ts`, `homeAction.ts`). Mudar o Shutdown para 18:00 fazia o
Agendador disparar às 18h enquanto o push e a Mesa continuavam dizendo 19h.

O arquivo é JSON, e não um campo do `config.py`, por um motivo só: o
`sync-cron.ps1` precisa lê-lo, e `ConvertFrom-Json` é nativo do PowerShell.
Acoplar o instalador do cron ao venv quebraria no dia de reconstruir o ambiente.
"""
import json
import re
from datetime import datetime
from pathlib import Path

_ARQUIVO = Path(__file__).resolve().parent.parent / "ritos.json"

DIAS = {"segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"}
_DIA_SEMANA = {"segunda": 0, "terça": 1, "quarta": 2, "quinta": 3,
               "sexta": 4, "sábado": 5, "domingo": 6}

# Quanto um rito pode atrasar e ainda valer. Cobre com folga o retry do
# `nudge.ps1` esperando o BFF subir; NÃO cobre catch-up de boot, que é o que
# fazia os seis nudges do dia chegarem no mesmo segundo às 22:44.
TOLERANCIA_ATRASO_MIN = 90

# E quanto ele pode ADIANTAR. Existe só pra absorver jitter do agendador; o valor é
# pequeno de propósito, porque é este lado que fecha a madrugada: sem ele, qualquer
# entrega depois da meia-noite parece "antes da hora" e passa.
ADIANTAMENTO_MAX_MIN = 5
SCRIPTS = {"nudge", "digest"}
_HORA = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Rito semanal antes disto quebraria `review - 3h` no homeAction, que não faz
# rollover de dia da semana. Restrição explícita vale mais que rollover que
# ninguém exercita (WIKI-SPEC §3.3).
_MIN_SEMANAL = 3 * 60


def minutos(hora: str) -> int:
    """'18:30' -> 1110."""
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def validar(dados: list[dict]) -> list[dict]:
    slugs, tasks = set(), set()
    for r in dados:
        slug = r.get("slug")
        if not slug or slug in slugs:
            raise ValueError(f"slug ausente ou duplicado: {slug!r}")
        slugs.add(slug)

        task = r.get("task")
        if not task or task in tasks:
            # Duas tarefas com o mesmo nome: o segundo Register-ScheduledTask
            # -Force sobrescreveria o primeiro em silêncio.
            raise ValueError(f"task ausente ou duplicada: {task!r}")
        tasks.add(task)

        hora = r.get("hora", "")
        if not _HORA.match(hora):
            raise ValueError(f"hora inválida em {slug!r}: {hora!r}")

        dia = r.get("dia")
        if dia is not None and dia not in DIAS:
            raise ValueError(f"dia inválido em {slug!r}: {dia!r}")
        if dia is not None and minutos(hora) < _MIN_SEMANAL:
            raise ValueError(f"rito semanal antes das 03:00 em {slug!r}: {hora!r}")

        if r.get("script") not in SCRIPTS:
            raise ValueError(f"script inválido em {slug!r}: {r.get('script')!r}")
    return dados


def _carregar() -> list[dict]:
    return validar(json.loads(_ARQUIVO.read_text(encoding="utf-8")))


RITOS = _carregar()
_POR_SLUG = {r["slug"]: r for r in RITOS}


def rito(slug: str) -> dict:
    return _POR_SLUG[slug]


def hora(slug: str) -> str:
    return _POR_SLUG[slug]["hora"]


def hora_curta(slug: str) -> str:
    """'19:00' -> '19h'; '05:30' -> '5h30'. O formato que o Leo já lê nos nudges."""
    h, m = _POR_SLUG[slug]["hora"].split(":")
    return f"{int(h)}h" if m == "00" else f"{int(h)}h{m}"


def slugs_por_script(script: str) -> list[str]:
    return [r["slug"] for r in RITOS if r["script"] == script]


def atraso_minutos(slug: str, agora: datetime) -> int | None:
    """Minutos entre a hora nominal do rito HOJE e `agora`. Negativo = antes da hora.

    `None` quando o rito nem é de hoje: um rito semanal disparado em outro dia da
    semana não está atrasado, está no dia errado — e comparar só o horário deixaria
    o review de domingo 20h passar numa segunda 20h30.
    """
    r = _POR_SLUG[slug]
    dia = r.get("dia")
    if dia is not None and agora.weekday() != _DIA_SEMANA[dia]:
        return None
    h, m = r["hora"].split(":")
    nominal = agora.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    return int((agora - nominal).total_seconds() // 60)


def atrasado(slug: str, agora: datetime, tolerancia: int = TOLERANCIA_ATRASO_MIN) -> bool:
    """O rito está FORA da janela e não deve ser entregue.

    A janela fecha dos DOIS lados, e o lado de cima é o que a primeira versão errou:
    medindo minutos-do-dia, uma entrega depois da meia-noite produzia atraso NEGATIVO
    (00:30 contra 21:00 dava −1230) e passava como "ainda não deu a hora" — justo o
    caso do catch-up de boot que esta guarda existe para barrar. Só rejeitar
    `atraso > tolerancia` deixava a madrugada inteira aberta.

    O Agendador do Windows registra as tarefas com -StartWhenAvailable removido, mas
    isso só resolve o lado de cá: o `systemd` do VPS tem `Persistent=true` com o mesmo
    comportamento, e um serviço que volta do zero continua podendo disparar tudo junto.
    Por isso a guarda mora no servidor, onde vale pros dois.

    O silêncio é a resposta certa: entregar o toque das 5h30 às 22h44 não é melhor que
    não entregar, é pior — o dedupe do dia ainda marcaria o rito como enviado, e o
    aviso da hora certa sumiria junto.
    """
    atraso = atraso_minutos(slug, agora)
    if atraso is None:
        return True
    return not (-ADIANTAMENTO_MAX_MIN <= atraso <= tolerancia)
