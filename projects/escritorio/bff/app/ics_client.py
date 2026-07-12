"""Leitura best-effort dos calendários pessoais e profissionais via ICS."""

import time
from datetime import date, datetime, time as _time, timedelta
from zoneinfo import ZoneInfo

import httpx
import recurring_ical_events
from icalendar import Calendar

from . import store
from .config import settings

TZ = ZoneInfo("America/Sao_Paulo")


async def _fetch(url: str) -> str:
    """Busca o ICS sem registrar a URL secreta em logs, conforme a lei 7."""
    async with httpx.AsyncClient(timeout=settings.ics_timeout) as client:
        resposta = await client.get(url)
        resposta.raise_for_status()
        return resposta.text


def _eventos_do_payload(payload: str, fonte: str, ref: date) -> list[dict]:
    """Expande recorrências na janela civil do dia em São Paulo."""
    inicio = datetime.combine(ref, _time.min, tzinfo=TZ)
    fim = datetime.combine(ref + timedelta(days=1), _time.min, tzinfo=TZ)
    calendario = Calendar.from_ical(payload)
    componentes = recurring_ical_events.of(calendario).between(inicio, fim)

    eventos: list[dict] = []
    for componente in componentes:
        valor_inicio = componente.decoded("DTSTART")
        titulo = str(componente.get("SUMMARY", "(sem título)"))

        if isinstance(valor_inicio, datetime):
            if valor_inicio.tzinfo is None:
                valor_inicio = valor_inicio.replace(tzinfo=TZ)
            local = valor_inicio.astimezone(TZ)
            hora = local.strftime("%H:%M")
            inicio_ts: float | None = local.timestamp()
        elif isinstance(valor_inicio, date):
            hora = None
            inicio_ts = None
        else:
            continue

        eventos.append(
            {
                "hora": hora,
                "titulo": titulo,
                "fonte": fonte,
                "inicio_ts": inicio_ts,
            }
        )

    eventos.sort(
        key=lambda evento: (
            evento["hora"] is not None,
            evento["hora"] or "",
            evento["titulo"],
        )
    )
    return eventos


async def eventos_do_dia(ref: date) -> tuple[list[dict], dict[str, str]]:
    """Lê as duas fontes sem permitir que uma falha cale a agenda inteira.

    Cache velho é usado com estado explícito. Essa degradação factual segue a lei 4:
    o sistema informa o estado da fonte sem transformar indisponibilidade em julgamento.
    """
    fontes = {
        "gcal": settings.gcal_ics_url,
        "outlook": settings.outlook_ics_url,
    }
    estados: dict[str, str] = {}
    eventos: list[dict] = []
    agora = time.time()

    for fonte, url in fontes.items():
        if not url:
            estados[fonte] = "nao_configurado"
            continue

        cache = store.get_ics_cache(fonte)
        cache_fresco = (
            cache is not None
            and agora - float(cache["fetched"]) < settings.ics_cache_ttl
        )

        if cache_fresco:
            try:
                eventos.extend(_eventos_do_payload(cache["payload"], fonte, ref))
                estados[fonte] = "ok"
            except Exception:  # noqa: BLE001 - ICS inválido não derruba consumidores
                estados[fonte] = "erro"
            continue

        try:
            payload = await _fetch(url)
            eventos_fonte = _eventos_do_payload(payload, fonte, ref)
            store.set_ics_cache(fonte, payload)
            eventos.extend(eventos_fonte)
            estados[fonte] = "ok"
        except Exception:  # noqa: BLE001 - rede e conteúdo externo são best-effort
            if cache is None:
                estados[fonte] = "erro"
                continue
            try:
                eventos.extend(_eventos_do_payload(cache["payload"], fonte, ref))
                estados[fonte] = "cache"
            except Exception:  # noqa: BLE001 - cache inválido também falha fechado
                estados[fonte] = "erro"

    eventos.sort(
        key=lambda evento: (
            evento["hora"] is not None,
            evento["hora"] or "",
            evento["titulo"],
        )
    )
    return eventos, estados
